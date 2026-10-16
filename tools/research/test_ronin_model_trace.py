import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from ronin_model_trace import enum_entry, protected_stub, raw_resource_facts


class ModelTraceTests(unittest.TestCase):
    def test_enum_value_is_read_from_constructor_not_baked_in(self):
        owner = 'LExample;'
        ops = [('new-instance', 'v0, LExample;'), ('const-string', 'v3, TARGET'),
               ('const/4', 'v1, 2'), ('const/16', 'v2, 17'),
               ('invoke-direct', 'v0, v3, v1, v2, LExample;-><init>(Ljava/lang/String; I I)V'),
               ('return-void', '')]
        self.assertEqual(enum_entry(ops, owner, 'TARGET'), dict(name='TARGET', ordinal=2, value=17))
        ops[3] = ('const/16', 'v2, 29')
        self.assertEqual(enum_entry(ops, owner, 'TARGET')['value'], 29)

    def test_enum_range_calls_and_overwritten_registers(self):
        ops = [('const-string', 'v1, TARGET'), ('const/4', 'v2, 0'), ('const/16', 'v3, 9'),
               ('invoke-direct/range', 'v0 ... v3, LExample;-><init>(Ljava/lang/String; I I)V')]
        self.assertEqual(enum_entry(ops, 'LExample;', 'TARGET')['value'], 9)
        for overwrite in [('sget-object', 'v3, LExample;->unknown I'),
                          ('new-instance', 'v3, LExample;'), ('move-result-object', 'v3')]:
            with self.assertRaises(ValueError):
                enum_entry(ops[:3] + [overwrite] + ops[3:], 'LExample;', 'TARGET')

    def test_control_flow_unknown_instruction_and_duplicate_target_fail(self):
        with self.assertRaisesRegex(ValueError, 'control flow'):
            enum_entry([('if-eqz', 'v0, +004h')], 'LExample;', 'TARGET')
        with self.assertRaises(ValueError):
            enum_entry([('add-int', 'v0, v1, v2')], 'LExample;', 'TARGET')
        ops = [('const-string', 'v1, TARGET'), ('const/4', 'v2, 0'), ('const/4', 'v3, 1'),
               ('invoke-direct', 'v0, v1, v2, v3, LExample;-><init>(Ljava/lang/String; I I)V')]
        with self.assertRaises(ValueError):
            enum_entry(ops + ops, 'LExample;', 'TARGET')

    def test_stub_is_pattern_only_and_does_not_hide_real_work(self):
        self.assertTrue(protected_stub(['nop', 'const', 'nop', 'nop', 'return-void']))
        self.assertFalse(protected_stub(['nop', 'const', 'invoke-direct', 'nop', 'return-void']))
        self.assertFalse(protected_stub(['return-void']))
        self.assertFalse(protected_stub(['const/4', 'return']))

    def test_resource_names_do_not_assign_an_active_model(self):
        xml = b'<resources><public type="string" name="ignore" id="0x1"/><public type="raw" name="generic" id="0x2"/><public type="raw" name="other" id="0x3"/></resources>'
        rows = raw_resource_facts(xml, lambda rid: {2: ['res/DB.json'], 3: ['res/jy.json']}[rid])
        self.assertEqual(rows, [dict(id=2, name='generic', path='res/DB.json'), dict(id=3, name='other', path='res/jy.json')])
        self.assertTrue(all('model' not in row for row in rows))

    def test_wrong_hash_rejects_before_optional_import_or_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apk, output = root/'fake.apk', root/'out'
            apk.write_bytes(b'not an apk')
            tool = Path(__file__).with_name('ronin_model_trace.py')
            result = subprocess.run([sys.executable, str(tool), '--apk', str(apk), '--output', str(output)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'APK hash differs', result.stderr)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
