import tempfile
import unittest
from pathlib import Path
from ronin_balance_trace import matching_records, ordinal_enum, trace


class BalanceTraceTests(unittest.TestCase):
    def test_duplicate_name_ranges_are_retained_in_source_order(self):
        rows=[dict(name='balance_test',index=37,typeID=0,size=1,minValue=0,maxValue=m) for m in (1,255)]
        result=matching_records(rows,'balance_test')
        self.assertEqual([(r['resourceOrdinal'],r['maxValue']) for r in result],[(0,1),(1,255)])
        result[0]['maxValue']=99
        self.assertEqual(rows[0]['maxValue'],1)

    def test_missing_or_conflicting_layout_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'missing'):matching_records([],'balance_test')
        with self.assertRaisesRegex(ValueError,'layout'):
            matching_records([dict(name='balance_test',index=37,typeID=0,size=2,minValue=0,maxValue=255)],'balance_test')

    def test_ordinal_reader_refuses_control_flow_or_unresolved_values(self):
        with self.assertRaisesRegex(ValueError,'unsupported'):
            ordinal_enum([('if-eqz','v0, +002h')],'LEnum;')
        with self.assertRaisesRegex(ValueError,'unresolved'):
            ordinal_enum([('invoke-direct','v0, v1, v2, LEnum;-><init>(Ljava/lang/String; I)V')],'LEnum;')

    def test_unpinned_input_rejects_before_optional_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input';p.write_bytes(b'other app')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d)/'missing')
