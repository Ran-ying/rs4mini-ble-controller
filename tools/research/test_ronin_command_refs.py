import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_command_refs import BANKS,ENUM,CMDSET,PACK,enum_reference,literal_packet_candidates,gimbal_command_set_value,scan
class CommandReferenceTests(unittest.TestCase):
    def packet(self,cmdset=4,cmdid=13):
        return [('new-instance','v0, '+PACK),('const/4','v1, '+str(cmdset)),('iput','v1, v0, '+PACK+'->cmdSet I'),('const/16','v1, '+str(cmdid)),('iput','v1, v0, '+PACK+'->cmdId I')]

    def test_only_static_field_ops_are_enum_references(self):
        text='v0, '+ENUM+'->SetOnOrOff '+ENUM
        self.assertEqual(enum_reference('sget-object',text,{'SetOnOrOff'}),'SetOnOrOff')
        self.assertIsNone(enum_reference('const-string/jumbo',text,{'SetOnOrOff'}))
        self.assertIsNone(enum_reference('sget-object',text,{'Control'}))

    def test_literal_fields_link_to_same_packet(self):
        r=literal_packet_candidates(self.packet(),{13});self.assertEqual(len(r),1);self.assertEqual(r[0]['commandId'],13);self.assertEqual(r[0]['packetCreationInstructionIndex'],0)
        ops=self.packet();ops.insert(3,('new-instance','v0, '+PACK));self.assertEqual(literal_packet_candidates(ops,{13}),[])

    def test_gimbal_symbol_value_accessor_and_alias(self):
        ops=[('new-instance','v0, '+PACK),('move-object','v3, v0'),('sget-object','v1, '+CMDSET+'->GIMBAL '+CMDSET),('invoke-virtual','v1, '+CMDSET+'->value()I'),('move-result','v2'),('iput','v2, v3, '+PACK+'->cmdSet I'),('const/16','v2, 13'),('iput','v2, v3, '+PACK+'->cmdId I')]
        self.assertEqual(literal_packet_candidates(ops,{13})[0]['commandId'],13)

    def test_unknown_register_write_does_not_reuse_old_literal(self):
        ops=self.packet();ops.insert(4,('iget','v1, v4, Lunknown;->value I'));self.assertEqual(literal_packet_candidates(ops,{13}),[])
        ops=self.packet();ops.insert(4,('rem-int','v1, v2, v3'));self.assertEqual(literal_packet_candidates(ops,{13}),[])
        ops=self.packet();ops.insert(4,('move-wide','v0, v4'));self.assertEqual(literal_packet_candidates(ops,{13}),[])
        ops=self.packet();ops.insert(4,('move-result-wide','v0'));self.assertEqual(literal_packet_candidates(ops,{13}),[])

    def test_branches_discard_linear_state(self):
        for branch in [('if-eqz','v1, +003h'),('goto','+003h'),('packed-switch','v1, +003h')]:
            ops=self.packet();ops.insert(3,branch);self.assertEqual(literal_packet_candidates(ops,{13}),[])

    def test_other_command_sets_and_unknown_ids_excluded(self):
        self.assertEqual(literal_packet_candidates(self.packet(cmdset=3),{13}),[])
        self.assertEqual(literal_packet_candidates(self.packet(cmdid=255),{13}),[])

    def test_no_candidate_without_explicit_sendpack_object(self):
        self.assertEqual(literal_packet_candidates(self.packet()[1:],{13}),[])

    def test_wrong_apk_hash_before_optional_parser(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'other')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):scan(p,Path(d))

    def test_bank_hashes_checked_before_optional_parser(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'fixture')
            for bank in BANKS:(Path(d)/('business-%02d-code-restored.dex'%bank)).write_bytes(b'invalid')
            with patch('ronin_command_refs.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()):
                with self.assertRaisesRegex(ValueError,'restored bank hash mismatch: 00'):scan(p,Path(d))

    def test_cmdset_object_constructor_is_not_a_literal_class_argument(self):
        ops=[('new-instance','v0, '+CMDSET),('new-instance','v1, Ldji/midware/data/config/P3/CmdIdGimbal;'),('invoke-direct','v1, Ldji/midware/data/config/P3/CmdIdGimbal;-><init>()V'),('const-string/jumbo','v2, GIMBAL'),('const/4','v4, 4'),('invoke-direct','v0, v2, v4, v4, v1, '+CMDSET+'-><init>(Ljava/lang/String; I I Ldji/midware/data/config/P3/DJICmdSetBase;)V')]
        self.assertEqual(gimbal_command_set_value(ops),4)
        with self.assertRaises(ValueError):gimbal_command_set_value(ops[:4]+ops[5:])

    def test_cmdset_branch_is_not_evaluated(self):
        with self.assertRaises(ValueError):gimbal_command_set_value([('if-eqz','v0, +003h')])
