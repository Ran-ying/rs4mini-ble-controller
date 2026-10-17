import tempfile,unittest
from pathlib import Path
from ronin_subscription_trace import trace,constructor_records
from ronin_subscription_payloads import subscription_group_body,request_push_preset

class SubscriptionTraceTests(unittest.TestCase):
    def test_wrong_apk_rejected_before_optional_imports(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'apk';p.write_bytes(b'other')
            with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d)/'dex')

    def test_group_header_is_highest_channel_not_byte_length(self):
        self.assertEqual(subscription_group_body(36,[0,2,9]),bytes.fromhex('24090502'))
        self.assertEqual(subscription_group_body(36,[9,0,9,2]),bytes.fromhex('24090502'))

    def test_bitmap_boundaries_and_full_byte_channel(self):
        self.assertEqual(subscription_group_body(36,[7]),bytes.fromhex('240780'))
        self.assertEqual(subscription_group_body(36,[8]),bytes.fromhex('24080001'))
        full=subscription_group_body(36,[255]);self.assertEqual(len(full),34);self.assertEqual(full[:2],bytes.fromhex('24ff'));self.assertEqual(full[2:],bytes(31)+bytes([128]))

    def test_empty_is_omitted_not_remote_unsubscribe_packet(self):
        self.assertEqual(subscription_group_body(36,[]),b'')
        self.assertEqual(subscription_group_body(16,[0]),bytes.fromhex('100001'))
        self.assertEqual(subscription_group_body(50,[0]),bytes.fromhex('320001'))

    def test_invalid_channel_and_command_context_rejected(self):
        for c,ch in [(True,[0]),(256,[0]),(36,[True]),(36,[-1]),(36,[256]),(36,[1.5]),(36,'1')]:
            with self.assertRaises(ValueError):subscription_group_body(c,ch)

    def test_request_push_preserves_first_byte_and_unknown_preset(self):
        self.assertEqual(request_push_preset(bytes([99,88,1,0]),0)['sourceEnum'],'CUSTOM_2')
        unknown=request_push_preset(bytes([0,1,255]),0);self.assertEqual(unknown['rawValue'],255);self.assertIsNone(unknown['sourceEnum']);self.assertFalse(unknown['activePresetVerified'])

    def test_response_and_encrypted_push_contexts_rejected(self):
        for flags in (128,129,1,7,True):
            with self.assertRaises(ValueError):request_push_preset(bytes([0,0,1]),flags)
        with self.assertRaises(ValueError):request_push_preset(bytes([0,1]),0)

    def test_constructor_parser_refuses_unresolved_or_branchy_arguments(self):
        with self.assertRaises(ValueError):constructor_records([('if-eqz','v0, +003h')],'LExample;')
        with self.assertRaises(ValueError):constructor_records([('invoke-direct','v0, v1, v2, v3, LExample;-><init>(Ljava/lang/String; I I)V')],'LExample;')

    def test_channel_constructor_keeps_explicit_id_separate_from_ordinal(self):
        operations=[('const-string','v1, USER_PROFILE'),('const/16','v2, 12'),('const/4','v3, 0'),('const-string','v4, table_choice'),('const-class','v5, LGetter;'),('invoke-direct/range','v0 ... v5, LExample;-><init>(Ljava/lang/String; I I Ljava/lang/String; Ljava/lang/Class;)V')]
        self.assertEqual(constructor_records(operations,'LExample;')['USER_PROFILE']['arguments'],['USER_PROFILE',12,0,'table_choice','LGetter;'])
