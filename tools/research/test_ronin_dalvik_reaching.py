import unittest

from ronin_dalvik_reaching import classify, value_at


def prog(lines):
    out, off = [], 0
    for op, text, length in lines:
        out.append(dict(off=off, op=op, text=text, length=length))
        off += length
    return out


class ReachingTests(unittest.TestCase):
    def test_unsupported_write_invalidates_constant(self):
        p = prog([
            ('const/4', 'v1, 0', 2),
            ('add-int/lit8', 'v1, v1, 1', 4),
            ('invoke-virtual', 'v0, v1, LX;->setISPreview(I)LX;', 6),
            ('return-void', '', 2),
        ])
        r = classify(value_at(p, 2, 'v1', registers_size=2, ins_size=1))
        self.assertEqual(r['kind'], 'statically_unresolved')
        self.assertIn('unsupported_write', r['reason'])

    def test_branch_join_yields_const_set_not_nearest(self):
        # if-eqz v2 -> L1 ; const v1=0 ; goto L2 ; L1: const v1=1 ; L2: invoke
        p = prog([
            ('if-eqz', 'v2, +004h', 4),      # off0 -> off8
            ('const/4', 'v1, 0', 2),          # off4
            ('goto', '+2h', 2),               # off6 -> off10
            ('const/4', 'v1, 1', 2),          # off8
            ('invoke-virtual', 'v0, v1, LX;->setISPreview(I)LX;', 6),  # off10
            ('return-void', '', 2),
        ])
        r = classify(value_at(p, 4, 'v1', registers_size=3, ins_size=2))
        self.assertEqual(r, dict(kind='const_set', values=[0, 1]))

    def test_join_with_non_constant_is_unresolved(self):
        p = prog([
            ('if-eqz', 'v2, +004h', 4),
            ('const/4', 'v1, 0', 2),
            ('goto', '+2h', 2),
            ('iget', 'v1, v0, LX;->f I', 4),
            ('invoke-virtual', 'v0, v1, LX;->setISPreview(I)LX;', 6),
            ('return-void', '', 2),
        ])
        r = classify(value_at(p, 4, 'v1', registers_size=3, ins_size=2))
        self.assertEqual(r['kind'], 'statically_unresolved')

    def test_parameter_register(self):
        p = prog([
            ('invoke-virtual', 'v0, v1, LX;->setISPreview(I)LX;', 6),
            ('return-void', '', 2),
        ])
        r = classify(value_at(p, 0, 'v1', registers_size=2, ins_size=2))
        self.assertEqual(r, dict(kind='method_parameter', parameterRegisterIndex=1))
