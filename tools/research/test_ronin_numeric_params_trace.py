import tempfile
import unittest
from pathlib import Path
from ronin_numeric_params_trace import OWNER,SETTING,enum_names,cache_pairs,trace

class NumericParamsTraceTests(unittest.TestCase):
    def test_enum_name_uses_constructor_register_not_nearby_literal(self):
        source=[('new-instance','v0, '+SETTING),('const-string/jumbo','v1, FIELD'),('const/4','v2, 0'),
                ('const-string/jumbo','v3, wire_name'),('const-string/jumbo','v4, unrelated'),
                ('invoke-direct','v0, v1, v2, v3, '+SETTING+'-><init>(Ljava/lang/String; I Ljava/lang/String;)V'),('return-void','')]
        self.assertEqual(enum_names(source,SETTING),{'FIELD':'wire_name'})
        with self.assertRaisesRegex(ValueError,'duplicate'):enum_names(source+source,SETTING)

    def test_cache_mapping_checks_registers_and_stops_at_branch(self):
        row=[('const-string/jumbo','v1, PublicKey'),('sget-object','v2, '+OWNER+'->FIELD '+OWNER),
             ('invoke-interface','v0, v1, v2, Ljava/util/Map;->put(Ljava/lang/Object; Ljava/lang/Object;)Ljava/lang/Object;')]
        self.assertEqual(cache_pairs(row),{'PublicKey':'FIELD'})
        bad=row[:2]+[('invoke-interface','v0, v3, v4, Ljava/util/Map;->put(Ljava/lang/Object; Ljava/lang/Object;)Ljava/lang/Object;')]
        self.assertEqual(cache_pairs(bad),{})
        self.assertEqual(cache_pairs([('if-eqz','v0, +2h')]+row),{})

    def test_unsupported_enum_control_flow_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'unsupported'):enum_names([('goto','+2h')],SETTING)

    def test_wrong_apk_rejects_before_reading_banks_or_optional_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input';p.write_bytes(b'other app')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d)/'sdk',Path(d)/'ui')
