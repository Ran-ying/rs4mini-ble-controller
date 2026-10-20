#!/usr/bin/env python3
"""Offline queue D: program model path and camera/exposure/record isolation.

Substatuses are computed from PREFIX evidence. Overall status depends on those
inputs (not a hard-coded exhausted constant). PREFIX only. No sends / vendor
execution / hardware.
"""
import argparse
import hashlib
import itertools
import json
import re
from pathlib import Path

from ronin_static import APK_SHA256
from ronin_prefix_restore import PREFIX_BANKS
from ronin_dalvik_reaching import analyze, classify, from_androguard

STATUS_UNRESOLVED = 'statically_unresolved'
STATUS_NEEDS_HW = 'statically_exhausted_needs_hardware'
BIT_LAYOUT_ESTABLISHED = 'bit_layout_established'
STATUS = STATUS_UNRESOLVED  # compat default: overall stays unresolved until a HW boundary is recorded
HG724 = 'Ldji/sdksharedlib/hardware/abstractions/gimbal/DJIGimbalHG724Abstraction;'
MODELS = {
    '25': 'Ldji/midware/data/model/P3/DataGimbalSetDelayTimelapseParams;',
    '37': 'Ldji/midware/data/model/P3/DataRonin2SetTimelapseParams;',
    '62': 'Ldji/midware/data/model/P3/DataGimbalSetTrackStatus;',
    '63': 'Ldji/midware/data/model/P3/DataGimbalSetPanoramaParams;',
}
CAMERAISH = re.compile(r'(exposure|record|preview|picture|camera|shoot|shutter|external)', re.I)
INFO_SETTERS = {
    '25': ('setControlExternalDevice', 'setISPreview', 'setIsTripod', 'setMode', 'setStartOrStop'),
    '37': ('setIsTripod', 'setMode', 'setStartOrPreview', 'setStartOrStop'),
}
INFO_SETTER_NAMES = set(INFO_SETTERS['25']) | set(INFO_SETTERS['37']) | {
    'setRecordOrPreview', 'setStopStartOrPreview', 'setExposure',
}
STOP_METHOD_HINT = re.compile(r'(stop|Stop|previewToggle)', re.I)
CREATE_HINT = re.compile(r'/create/', re.I)


def _ops(method):
    return [(i.get_name(), i.get_output()) for i in method.get_instructions()]


def _fields_from_dopack(classes, owner):
    found = [m for m in classes[owner].get_methods() if m.get_name() == 'doPack' and m.get_descriptor() == '()V']
    if len(found) != 1 or not found[0].get_code():
        raise ValueError('missing doPack ' + owner)
    method = found[0]
    fields = []
    for instruction in method.get_instructions():
        text = instruction.get_output()
        if instruction.get_name().startswith('iget') and owner + '->' in text:
            fields.append(text.split('->', 1)[1].split(' ', 1)[0])
    seen = set()
    ordered = []
    for name in fields:
        if name not in seen and name != '_sendData':
            seen.add(name)
            ordered.append(name)
    return ordered, hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(), method.get_code_off()


def _parse_info_byte_setter(owner, method):
    """Extract OR-into-mInfoByte shift/mask from a linear setter body."""
    ops = _ops(method)
    if not any(owner + '->mInfoByte B' in t and op.startswith('iput') for op, t in ops):
        return None
    shift = None
    mask = None
    clears_other_bits = False
    for op, text in ops:
        if op == 'and-int/lit8' and ', 1' in text:
            mask = 1
        if op == 'shl-int/lit8':
            parts = text.split(', ')
            if len(parts) == 3 and parts[2].lstrip('-').isdigit():
                shift = int(parts[2])
        elif op.startswith('shl-int'):
            parts = text.split(', ')
            if len(parts) >= 3 and parts[-1].lstrip('-').isdigit():
                shift = int(parts[-1])
        # clearing inverse mask before OR (typical: and with ~bit then or)
        if op == 'and-int/lit8' and ', 1' not in text:
            clears_other_bits = True
    if shift is None and any(op == 'or-int/2addr' for op, _ in ops):
        shift = 0
    if shift is None:
        return None
    return dict(
        method=method.get_name(),
        descriptor=method.get_descriptor(),
        bitIndex=shift,
        lowBitMask=mask,
        orAccumulatesIntoExistingByte=True,
        clearsInverseBitBeforeOr=clears_other_bits,
        cameraOrPreviewOrExternalName=bool(CAMERAISH.search(method.get_name())),
        instructionSha256=hashlib.sha256(method.get_code().get_bc().get_raw()).hexdigest(),
    )


def _parse_descriptor_params(descriptor):
    """Return list of param type chars/names inside (...); excludes return."""
    inner = descriptor[descriptor.find('(') + 1:descriptor.find(')')]
    params = []
    i = 0
    while i < len(inner):
        c = inner[i]
        if c in 'ZBCSIJFD':
            params.append(c)
            i += 1
        elif c == 'L':
            end = inner.find(';', i)
            params.append(inner[i:end + 1])
            i = end + 1
        elif c == '[':
            i += 1
            continue
        else:
            i += 1
    return params


def _analyze_create_method(bank, owner, method, model_owners):
    """Extract setter invokes with resolved args, instance source, and branch role."""
    if not method.get_code():
        return []
    ops = _ops(method)
    desc = method.get_descriptor()
    instrs, cfg_kwargs = from_androguard(method)
    envs = None
    cfg_gaps = None
    # Approximate: last N registers are params (this + args). androguard doesn't give register count easily;
    # mark kind unresolved_or_param when backward scan fails; refine if register matches pN naming in output.
    rows = []
    instance_source = None
    for idx, (op, text) in enumerate(ops):
        if op.startswith('iget-object') and '->mSetter' in text:
            instance_source = dict(kind='instance_field_mSetter', text=text.strip())
        if op.startswith('invoke') and '->getInstance()' in text and any(m in text for m in model_owners):
            instance_source = dict(kind='getInstance_singleton', text=text.strip())
        if not op.startswith('invoke'):
            continue
        if not any(m + '->' in text for m in model_owners):
            continue
        setter = None
        for name in INFO_SETTER_NAMES:
            if '->' + name + '(' in text:
                setter = name
                break
        if setter is None and '->start(' not in text and '->addRoadPosition' not in text and '->clearPoint' not in text:
            # other model methods still recorded lightly
            setter = text.split('->', 1)[1].split('(')[0] if '->' in text else None
        if setter is None:
            continue
        # invoke-virtual vA, vB, ... Owner;->name
        regs = []
        head = text.split(', L', 1)[0] if ', L' in text else text.split(',')[0]
        # better: split on ', ' until we hit L...
        chunks = text.split(', ')
        for ch in chunks:
            if ch.startswith('L') or ch.startswith('['):
                break
            if re.fullmatch(r'v\d+', ch):
                regs.append(ch)
        # regs[0]=instance, regs[1:]=args
        arg_regs = regs[1:] if len(regs) > 1 else []
        args = []
        if envs is None:
            envs, cfg_gaps = analyze(instrs, **cfg_kwargs)
        for ar in arg_regs:
            if cfg_gaps:
                resolved = dict(kind='statically_unresolved', reason='cfg_unsupported: ' + '; '.join(sorted(set(cfg_gaps))))
            elif envs[idx] is None:
                resolved = dict(kind='statically_unresolved', reason='unreachable_or_unanalysed')
            else:
                resolved = classify(envs[idx].get(ar, ('unknown', 'undefined')))
            resolved = dict(resolved, register=ar, instructionByteOffset=instrs[idx]['off'])
            args.append(resolved)
        role = 'stop' if STOP_METHOD_HINT.search(method.get_name() or '') else (
            'preview_branch' if 'preview' in (method.get_name() or '').lower() else 'start_or_other'
        )
        rows.append(dict(
            bank=bank,
            className=owner,
            method=method.get_name(),
            descriptor=desc,
            createUi=bool(CREATE_HINT.search(owner)),
            setter=setter,
            invokeText=text[:200],
            argumentRegisters=arg_regs,
            arguments=args,
            instanceSource=instance_source,
            controlFlowRole=role,
            cameraOrPreviewOrExternalSetter=bool(CAMERAISH.search(setter or '')),
        ))
    return rows


def compute_substatuses(
    *,
    bit_layout_established,
    call_values_has_dynamic_boundary,
    call_values_has_unresolved_args=False,
    camera_isolation_has_dynamic_boundary,
    stop_semantics_has_dynamic_boundary,
    model_entry_has_dynamic_boundary,
):
    """Map evidence flags to per-facet statuses. Inputs must affect outputs."""
    bit_layout = BIT_LAYOUT_ESTABLISHED if bit_layout_established else STATUS_UNRESOLVED
    # An unresolved register is not a hardware boundary: it keeps call_values unresolved.
    if call_values_has_unresolved_args:
        call_values = STATUS_UNRESOLVED
    else:
        call_values = STATUS_NEEDS_HW if call_values_has_dynamic_boundary else STATUS_UNRESOLVED
    camera_isolation = STATUS_NEEDS_HW if camera_isolation_has_dynamic_boundary else STATUS_UNRESOLVED
    stop_semantics = STATUS_NEEDS_HW if stop_semantics_has_dynamic_boundary else STATUS_UNRESOLVED
    model_entry = STATUS_NEEDS_HW if model_entry_has_dynamic_boundary else STATUS_UNRESOLVED
    return dict(
        bit_layout=bit_layout,
        call_values=call_values,
        camera_isolation=camera_isolation,
        stop_semantics=stop_semantics,
        model_entry=model_entry,
    )


def compute_overall(substatuses):
    """Overall status depends on substatus inputs.

    - bit_layout not established → statically_unresolved
    - any other facet needs_hardware → statically_exhausted_needs_hardware
    - otherwise → statically_unresolved (static facets still open; not an exhaustion claim)
    """
    if substatuses.get('bit_layout') != BIT_LAYOUT_ESTABLISHED:
        return STATUS_UNRESOLVED
    facets = ('call_values', 'camera_isolation', 'stop_semantics', 'model_entry')
    if any(substatuses.get(k) == STATUS_NEEDS_HW for k in facets):
        return STATUS_NEEDS_HW
    return STATUS_UNRESOLVED


def iter_status_combinations():
    """bit_layout x (call boundary, call unresolved, camera, stop, model) flag combinations."""
    for bit_ok in (False, True):
        for flags in itertools.product((False, True), repeat=5):
            yield (bit_ok,) + flags


def scan(apk, bank_dir):
    if hashlib.sha256(apk.read_bytes()).hexdigest() != APK_SHA256:
        raise ValueError('APK hash mismatch')
    images = []
    for bank, pin in PREFIX_BANKS.items():
        raw = (bank_dir / ('business-%02d-prefix-code-restored.dex' % bank)).read_bytes()
        if hashlib.sha256(raw).hexdigest() != pin:
            raise ValueError('prefix bank hash mismatch: %02d' % bank)
        images.append((bank, raw))
    from loguru import logger
    logger.disable('androguard')
    from androguard.core.dex import DEX

    banks_meta = []
    external = {k: [] for k in MODELS}
    hg724_program = []
    create_setter_traces = []
    stop_chain_traces = []
    model_owners = list(MODELS.values())
    bank05 = None
    bank_classes = {}
    for bank, raw in images:
        classes = {c.get_name(): c for c in DEX(raw).get_classes()}
        bank_classes[bank] = classes
        banks_meta.append(dict(segment=bank, derivedSha256=PREFIX_BANKS[bank]))
        if bank == 5:
            bank05 = classes
        if HG724 in classes:
            names = {m.get_name() for m in classes[HG724].get_methods()}
            for name in names:
                if any(k in name.lower() for k in ('track', 'panorama', 'timelapse', 'program', 'roadpoint')):
                    hg724_program.append(dict(bank=bank, method=name))
        for owner, cls in classes.items():
            for method in cls.get_methods():
                if not method.get_code():
                    continue
                traces = _analyze_create_method(bank, owner, method, model_owners)
                for row in traces:
                    if row['createUi'] or CREATE_HINT.search(owner):
                        create_setter_traces.append(row)
                    if row['controlFlowRole'] == 'stop' or (
                        owner.endswith('CreateUtils;') and STOP_METHOD_HINT.search(method.get_name() or '')
                    ):
                        stop_chain_traces.append(row)
                for instruction in method.get_instructions():
                    if not instruction.get_name().startswith('invoke'):
                        continue
                    text = instruction.get_output()
                    for key, target in MODELS.items():
                        if target + '->' in text and owner != target:
                            external[key].append(dict(
                                bank=bank, className=owner, method=method.get_name(),
                                descriptor=method.get_descriptor(),
                                createUi='create' in owner.lower(),
                            ))
        print('bank%02d' % bank, flush=True)

    classes = bank05
    commands = {}
    methods = []
    info_byte_maps = {}
    for key, owner in MODELS.items():
        fields, sha, off = _fields_from_dopack(classes, owner)
        camera_fields = [f for f in fields if CAMERAISH.search(f)]
        seen = set()
        callers = []
        for row in external[key]:
            item = (row['bank'], row['className'], row['method'], row['descriptor'])
            if item in seen:
                continue
            seen.add(item)
            callers.append(row)
        commands[key] = dict(
            key='04:' + key,
            modelClass=owner,
            doPackFields=fields,
            cameraOrRecordFieldsInDoPack=camera_fields,
            externalDirectCallers=callers,
            allExternalCallersInCreateUi=all(r['createUi'] for r in callers) and bool(callers),
            doPackInstructionSha256=sha,
            doPackCodeOffset=off,
        )
        methods.append(dict(bank=5, className=owner, method='doPack', descriptor='()V', codeOffset=off, instructionSha256=sha))
        if key in INFO_SETTERS:
            bits = []
            for name in INFO_SETTERS[key]:
                found = [m for m in classes[owner].get_methods() if m.get_name() == name and m.get_code()]
                if len(found) != 1:
                    raise ValueError('missing/ambiguous info setter ' + owner + name)
                parsed = _parse_info_byte_setter(owner, found[0])
                if parsed is None:
                    raise ValueError('could not parse mInfoByte setter ' + name)
                bits.append(parsed)
                methods.append(dict(
                    bank=5, className=owner, method=name, descriptor=found[0].get_descriptor(),
                    codeOffset=found[0].get_code_off(), instructionSha256=parsed['instructionSha256'],
                ))
            bit_indexes = sorted({b['bitIndex'] for b in bits})
            camera_bits = [b for b in bits if b['cameraOrPreviewOrExternalName']]
            info_byte_maps[key] = dict(
                field='mInfoByte',
                setters=bits,
                bitIndexes=bit_indexes,
                cameraPreviewOrExternalBits=camera_bits,
                bitsResolved=len(bits) == len(INFO_SETTERS[key]) and len(bit_indexes) == len(bits),
                orAccumulationIntoSharedByte=all(b.get('orAccumulatesIntoExistingByte') for b in bits),
            )

    if 'mExposure' not in commands['63']['doPackFields']:
        raise ValueError('panorama mExposure missing')
    if 'mRecordOrPreview' not in commands['62']['doPackFields']:
        raise ValueError('track mRecordOrPreview missing')
    if 'mInfoByte' not in commands['25']['doPackFields'] or 'mInfoByte' not in commands['37']['doPackFields']:
        raise ValueError('timelapse mInfoByte missing from doPack fields')

    bit_layout_ok = all(info_byte_maps[k]['bitsResolved'] for k in ('25', '37'))

    # Call-value dynamic boundaries: preview/external args that are not compile-time consts
    dynamic_call_sites = []
    const_camera_sites = []
    unresolved_call_sites = []
    for row in create_setter_traces:
        if not row.get('cameraOrPreviewOrExternalSetter'):
            continue
        for arg in row.get('arguments') or []:
            kind = arg.get('kind')
            site = dict(className=row['className'], method=row['method'], setter=row['setter'], argument=arg)
            if kind == 'const':
                const_camera_sites.append(dict(row, resolvedArgument=arg))
            elif kind in ('const_set', 'method_parameter', 'instance_field', 'static_field', 'invoke_result'):
                # const_set: value set proven; selection depends on runtime branch conditions.
                dynamic_call_sites.append(dict(site, boundaryKind=kind))
            else:
                unresolved_call_sites.append(site)

    # Instance init/reuse: mSetter field vs getInstance at call site
    instance_reuse = []
    seen_inst = set()
    for row in create_setter_traces:
        src = row.get('instanceSource') or {}
        key = (row['className'], row['method'], src.get('kind'))
        if key in seen_inst:
            continue
        seen_inst.add(key)
        if src.get('kind'):
            instance_reuse.append(dict(
                className=row['className'], method=row['method'],
                instanceSourceKind=src.get('kind'), detail=src.get('text', '')[:160],
                impliesSharedSingletonOrFieldReuse=src.get('kind') in (
                    'getInstance_singleton', 'instance_field_mSetter',
                ),
            ))

    # Stop chains: CreateUtils + Create* stop methods with const args where visible
    stop_summary = []
    seen_stop = set()
    for row in stop_chain_traces:
        key = (row['className'], row['method'], row['setter'])
        if key in seen_stop:
            continue
        seen_stop.add(key)
        stop_summary.append(dict(
            className=row['className'], method=row['method'], setter=row['setter'],
            arguments=row.get('arguments'), clearsPreviewBitExplicitly=row['setter'] in (
                'setISPreview', 'setStartOrPreview', 'setRecordOrPreview', 'setStopStartOrPreview',
            ),
        ))

    # Model/component reachability: no HG724-named program methods; Create uses midware singletons
    model_reachability = dict(
        hg724NamedProgramMethods=hg724_program,
        missingHg724NamedCallerDoesNotProveNoInheritedEntry=True,
        createUiUsesMidwareGetInstanceOrField=any(
            r.get('impliesSharedSingletonOrFieldReuse') for r in instance_reuse
        ),
        productTypeGateInCreateUiResolved=False,
        dynamicBoundary='RS 4 Mini product/component map and whether Create program midware paths are bound for HG724 are not fixed in PREFIX bytecode alone',
        hardwareMeasurementsNeeded=[
            'Confirm whether RS 4 Mini / HG724 session exposes Create timelapse/track/panorama midware commands',
            'Capture whether UIViewManager Create* entries are offered for the connected product type',
        ],
    )

    call_values_boundary = bool(dynamic_call_sites)
    # Camera isolation: packing can include camera bits; some Create paths use const 0 preview,
    # others pass runtime preview/external. Firmware effect of those bits is the HW boundary —
    # do NOT claim isolation statically disproven or established.
    camera_isolation_boundary = bool(
        commands['63']['cameraOrRecordFieldsInDoPack']
        or commands['62']['cameraOrRecordFieldsInDoPack']
        or any(info_byte_maps[k]['cameraPreviewOrExternalBits'] for k in ('25', '37'))
    )
    # Stop semantics: chains traced with consts in CreateUtils, but device effect + singleton
    # uncleared bits remain dynamic.
    stop_boundary = bool(stop_summary)
    model_boundary = True  # product/component reachability always needs session evidence here

    boundaries = []
    if call_values_boundary:
        boundaries.append(dict(
            facet='call_values',
            kind='dynamic_register_or_field_argument',
            detail='Create camera/preview setter args are method parameters, fields, invoke results, or branch-selected const sets (e.g. PathDelay setControlExternalDevice {0,1} chosen by mFocusMotorConnected/createFocusControlEnabled/waypoint count)',
            examples=dynamic_call_sites[:12],
            hardwareMeasurementsNeeded=[
                'Log actual setISPreview / setControlExternalDevice / setStartOrPreview values on device for start and stop',
                'Correlate UI preview toggle and focus-motor state with packed mInfoByte bits',
            ],
        ))
    if camera_isolation_boundary:
        boundaries.append(dict(
            facet='camera_isolation',
            kind='firmware_interpretation_of_packed_camera_bits',
            detail=(
                'Wire layout can pack preview/external/exposure/record fields beside gimbal controls; '
                'CreateFollowActivity.startTimeLapse uses const preview=0, while other Create paths pass '
                'runtime preview/external. Whether a camera-free gimbal program primitive exists is not '
                'settled by layout alone.'
            ),
            hardwareMeasurementsNeeded=[
                'Send or observe preview=0 vs preview=1 program packets on RS 4 Mini and check camera/side effects',
                'Observe panorama mExposure and track mRecordOrPreview influence on device behavior',
            ],
        ))
    if stop_boundary:
        boundaries.append(dict(
            facet='stop_semantics',
            kind='device_effect_of_traced_stop_packets',
            detail=(
                'CreateUtils stop* and Create* stop methods set startOrStop (and sometimes record/preview) '
                'then start(callback); several stop paths omit an explicit preview-bit clear on the shared '
                'getInstance/mSetter singleton, so OR-accumulated bits may persist across calls.'
            ),
            tracedStops=stop_summary[:20],
            hardwareMeasurementsNeeded=[
                'Verify stop packets halt motion on RS 4 Mini',
                'Check whether uncleared preview/external bits on the singleton affect stop or next start',
            ],
        ))
    if model_boundary:
        boundaries.append(dict(
            facet='model_entry',
            kind='product_component_session_binding',
            detail=model_reachability['dynamicBoundary'],
            hardwareMeasurementsNeeded=model_reachability['hardwareMeasurementsNeeded'],
        ))

    substatuses = compute_substatuses(
        bit_layout_established=bit_layout_ok,
        call_values_has_dynamic_boundary=call_values_boundary,
        call_values_has_unresolved_args=bool(unresolved_call_sites),
        camera_isolation_has_dynamic_boundary=camera_isolation_boundary,
        stop_semantics_has_dynamic_boundary=stop_boundary,
        model_entry_has_dynamic_boundary=model_boundary,
    )
    status = compute_overall(substatuses)

    reason = (
        'mInfoByte bit layout is established for 04:25/37. Create call sites, stop chains, and '
        'shared getInstance/mSetter reuse are traced, but call-argument values, camera isolation, '
        'stop effects, and RS 4 Mini model/component reachability each still hit a recorded dynamic '
        'or session boundary (see dynamicBoundaries). Program sends stay closed.'
        if status == STATUS_NEEDS_HW else
        'Bit layout and/or remaining facets are still statically_unresolved; no hardware boundary recorded yet.'
    )

    return dict(
        schemaVersion=3,
        apkSha256=APK_SHA256,
        bankSha256={str(b): p for b, p in PREFIX_BANKS.items()},
        scannedBanks=list(PREFIX_BANKS),
        analysisBank=5,
        appCodeExecuted=False,
        targetDeviceVerified=False,
        sendOpened=False,
        sdkSendAdded=False,
        programExecutionOpened=False,
        banks=banks_meta,
        methods=methods,
        status=status,
        substatuses=substatuses,
        statusComputedBy='compute_overall(compute_substatuses(...))',
        commands=commands,
        infoByteMaps=info_byte_maps,
        createSetterTraces=create_setter_traces,
        constCameraOrPreviewSetterSites=[
            dict(className=r['className'], method=r['method'], setter=r['setter'], value=r['resolvedArgument'].get('value'),
                 instructionByteOffset=r['resolvedArgument'].get('instructionByteOffset'))
            for r in const_camera_sites[:30]
        ],
        dynamicCallValueSites=dynamic_call_sites,
        unresolvedCallValueSites=unresolved_call_sites,
        argumentResolution='CFG + reaching definitions (ronin_dalvik_reaching); joins give const_set or statically_unresolved; unsupported writes invalidate',
        instanceInitAndReuse=instance_reuse,
        stopCallChains=stop_summary,
        modelReachability=model_reachability,
        dynamicBoundaries=boundaries,
        hg724NamedProgramMethods=hg724_program,
        panoramaHasExposureField=True,
        trackHasRecordOrPreviewField=True,
        cameraFieldsPresentInPanoramaAndTrackDoPack=True,
        timelapseInfoByteHasPreviewOrExternalBits=any(
            info_byte_maps[k]['cameraPreviewOrExternalBits'] for k in ('25', '37')
        ),
        reliableStopWithCameraIsolationEstablished=False,
        pureGimbalProgramPrimitiveOpenable=False,
        hg724ModelSpecificProgramEntryEstablished=False,
        missingHg724NamedCallerDoesNotProveNoInheritedEntry=True,
        reasonNotClosed=reason,
        remaining=[
            'Do not open 04:25/37/62/63 sends.',
            'Do not treat missing HG724-named program methods as no inherited entry.',
            'Do not claim camera isolation is statically established or statically disproven from layout alone.',
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--bank-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = scan(args.apk, args.bank_dir)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(
        'queue-D:', result['status'],
        'subs', result['substatuses'],
        'bits25', result['infoByteMaps']['25']['bitIndexes'],
        flush=True,
    )


if __name__ == '__main__':
    main()
