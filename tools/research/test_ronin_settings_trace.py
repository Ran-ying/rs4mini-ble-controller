import unittest
from ronin_settings_trace import OWNER, named_keys, unique_record


class SettingsTraceTests(unittest.TestCase):
    def test_named_key_tracks_constructor_fields_not_numeric_enum(self):
        operations = [('new-instance', 'v0, '+OWNER), ('const-string/jumbo', 'v1, FIELD'),
                      ('const/4', 'v2, 0'), ('const/4', 'v3, 99'),
                      ('const-string/jumbo', 'v4, named_parameter'), ('const-class', 'v5, Lexample/Getter;'),
                      ('invoke-direct/range', 'v0 ... v5, '+OWNER+'-><init>(Ljava/lang/String; I I Ljava/lang/String; Ljava/lang/Class;)V')]
        self.assertEqual(named_keys(operations), dict(FIELD=dict(name='named_parameter', getter='Lexample/Getter;')))
        with self.assertRaises(ValueError):
            named_keys(operations + [('if-eqz', 'v1, +001h')])

    def test_duplicate_wire_indexes_do_not_override_named_lookup(self):
        def row(name):
            return dict(name=name,index=132,size=1,typeID=0,minValue=0,maxValue=15)
        records = [row('a'), row('b')]
        self.assertEqual(unique_record(records, 'b')['name'], 'b')
        with self.assertRaises(ValueError):
            unique_record(records+[row('b')], 'b')
        with self.assertRaises(ValueError):
            unique_record(records, 'missing')

    def test_unresolved_key_constructor_is_rejected(self):
        with self.assertRaises(ValueError):
            named_keys([('invoke-direct', 'v0, v1, v2, v3, '+OWNER+'-><init>(Ljava/lang/String; I Ljava/lang/String;)V')])
