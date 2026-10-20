"""Conservative CFG + reaching-definition value analysis for Dalvik registers.

Pure Python (no androguard) so it can be unit-tested with synthetic methods.
Instructions are dicts: {'off': byte offset, 'op': mnemonic, 'text': operands,
'length': bytes}. Values are abstract:
  ('consts', frozenset[int])          provable constant set
  ('param', n)                        method-entry register (parameter n / this)
  ('entry',)                          uninitialised at entry (non-parameter)
  ('field', kind, text)               last write was an iget/sget
  ('result', text)                    last write was move-result of an invoke
  ('unknown', reason)                 unsupported write, mixed join, or CFG gap
"""
import re

BRANCH_RE = re.compile(r'([+-])([0-9a-fA-F]+)h$')
NO_WRITE_PREFIXES = (
    'invoke', 'if-', 'goto', 'return', 'iput', 'sput', 'aput', 'throw', 'monitor-',
    'fill-array-data', 'nop', 'packed-switch', 'sparse-switch',
)
TERMINATORS = ('return', 'throw', 'goto')


def _regs(text):
    out = []
    for chunk in text.split(', '):
        chunk = chunk.strip()
        if re.fullmatch(r'v\d+', chunk):
            out.append(chunk)
        else:
            break
    return out


def _branch_target(ins):
    match = BRANCH_RE.search(ins['text'].strip())
    if not match:
        return None
    rel = int(match.group(2), 16) * (1 if match.group(1) == '+' else -1)
    return ins['off'] + rel * 2


def _join(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a[0] == 'consts' and b[0] == 'consts':
        return ('consts', a[1] | b[1])
    if a == b:
        return a
    return ('unknown', 'branch_join_of_non_constant_or_mixed_definitions')


def _join_env(envs):
    keys = set()
    for env in envs:
        keys |= set(env)
    out = {}
    for key in keys:
        value = None
        for env in envs:
            value = _join(value, env.get(key, ('unknown', 'undefined_on_some_path')))
        out[key] = value
    return out


def _transfer(ins, env, prev_invoke):
    op, text = ins['op'], ins['text']
    env = dict(env)
    if op.startswith(NO_WRITE_PREFIXES):
        return env
    regs = _regs(text)
    if not regs:
        return env
    dst = regs[0]
    wide = 'wide' in op
    def write(value):
        env[dst] = value
        if wide:
            env['v%d' % (int(dst[1:]) + 1)] = ('unknown', 'wide_pair_high_half')
    if op.startswith('const') and not wide and not op.startswith(('const-string', 'const-class')):
        lit = text.split(', ')[-1].strip()
        try:
            write(('consts', frozenset([int(lit, 0)])))
        except ValueError:
            write(('unknown', 'unparsed_const: ' + lit))
    elif op in ('move', 'move/from16', 'move/16', 'move-object', 'move-object/from16', 'move-object/16') and len(regs) >= 2:
        write(env.get(regs[1], ('unknown', 'undefined_source')))
    elif op.startswith('move-result'):
        write(('result', prev_invoke or '?'))
    elif op.startswith('iget'):
        write(('field', 'instance_field', text.split('->', 1)[-1].strip()))
    elif op.startswith('sget'):
        write(('field', 'static_field', text.split('->', 1)[-1].strip()))
    else:
        write(('unknown', 'unsupported_write: ' + op))
    return env


def analyze(instructions, registers_size=None, ins_size=0, handler_offsets=()):
    """Return list of IN environments, one per instruction index."""
    by_off = {ins['off']: i for i, ins in enumerate(instructions)}
    succ = [[] for _ in instructions]
    unsupported = []
    for i, ins in enumerate(instructions):
        op = ins['op']
        if op.startswith(('packed-switch', 'sparse-switch')):
            unsupported.append('switch_targets_not_modelled')
        if op.startswith('if-') or op.startswith('goto'):
            target = _branch_target(ins)
            if target is None or target not in by_off:
                unsupported.append('unresolved_branch_target at %d' % ins['off'])
            else:
                succ[i].append(by_off[target])
        if not op.startswith(TERMINATORS) and i + 1 < len(instructions):
            succ[i].append(i + 1)
    preds = [[] for _ in instructions]
    for i, targets in enumerate(succ):
        for t in targets:
            preds[t].append(i)
    entry = {}
    if registers_size:
        first_param = registers_size - ins_size
        for r in range(registers_size):
            entry['v%d' % r] = ('param', r - first_param) if r >= first_param else ('entry',)
    handler_idx = {by_off[o] for o in handler_offsets if o in by_off}
    ins_env = [None] * len(instructions)
    out_env = [None] * len(instructions)
    prev_invoke = [None] * len(instructions)
    for i, ins in enumerate(instructions):
        if i and instructions[i - 1]['op'].startswith('invoke'):
            prev_invoke[i] = instructions[i - 1]['text'].split(', L', 1)[-1][:160]
    changed = True
    rounds = 0
    while changed and rounds < 200:
        changed = False
        rounds += 1
        for i, ins in enumerate(instructions):
            sources = [out_env[p] for p in preds[i] if out_env[p] is not None]
            if i == 0:
                sources.append(entry)
            if i in handler_idx:
                # exceptional edge: any instruction may have thrown; join everything seen
                sources.extend(e for e in out_env if e is not None)
            new_in = _join_env(sources) if sources else None
            if new_in is None:
                continue
            new_out = _transfer(ins, new_in, prev_invoke[i])
            if new_in != ins_env[i] or new_out != out_env[i]:
                ins_env[i], out_env[i] = new_in, new_out
                changed = True
    return ins_env, unsupported


def value_at(instructions, index, register, **kwargs):
    envs, unsupported = analyze(instructions, **kwargs)
    if unsupported:
        return ('unknown', 'cfg_unsupported: ' + '; '.join(sorted(set(unsupported))))
    env = envs[index]
    if env is None:
        return ('unknown', 'unreachable_or_unanalysed')
    return env.get(register, ('unknown', 'undefined'))


def classify(value):
    """Map abstract value to evidence dict (honest kinds; unknown stays unresolved)."""
    kind = value[0]
    if kind == 'consts':
        vals = sorted(value[1])
        if len(vals) == 1:
            return dict(kind='const', value=vals[0])
        return dict(kind='const_set', values=vals)
    if kind == 'param':
        return dict(kind='method_parameter', parameterRegisterIndex=value[1])
    if kind == 'field':
        return dict(kind=value[1], field=value[2])
    if kind == 'result':
        return dict(kind='invoke_result', source=value[1])
    if kind == 'entry':
        return dict(kind='statically_unresolved', reason='uninitialised_at_entry')
    return dict(kind='statically_unresolved', reason=value[1])


def from_androguard(method):
    """Build instruction dicts with real byte offsets (accumulated get_length())."""
    code = method.get_code()
    out = []
    off = 0
    for ins in method.get_instructions():
        out.append(dict(off=off, op=ins.get_name(), text=ins.get_output(), length=ins.get_length()))
        off += ins.get_length()
    handlers = []
    try:
        for handler in code.get_handlers().get_list():
            for pair in handler.get_handlers():
                handlers.append(pair.get_addr() * 2)
            if handler.get_size() <= 0:
                handlers.append(handler.get_catch_all_addr() * 2)
    except Exception:
        pass
    return out, dict(
        registers_size=code.get_registers_size(),
        ins_size=code.get_ins_size(),
        handler_offsets=tuple(handlers),
    )
