import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_balance_adjust import source_request_body,decimal_pair,source_business_body,invoked_owner,trace,REQUESTS,STATUS,RESULT,SET,PUSH,BANKS

class BalanceAdjustTests(unittest.TestCase):
    def test_request_values_are_wire_values_not_ordinals(self):
        expected={'PITCH_TEST':'000101','PITCH_ADJUST':'000102','ROLL_TEST':'000104','ROLL_ADJUST':'000108','YAW_TEST':'000110','YAW_ADJUST':'000120','STOP_ADJUST':'000140','OTHER':'000164'}
        self.assertEqual({name:source_request_body(name).hex() for name in REQUESTS},expected)
    def test_request_domain_is_explicit_source_names(self):
        for value in [None,True,0,64,'STOP','stop_adjust',[],{}]:
            with self.assertRaises(ValueError):source_request_body(value)
    def test_decimal_binary_pair_is_not_standard_bit_value(self):
        for pair,want in enumerate([0,1,10,11]):
            for shift in [0,2,4,6]:self.assertEqual(decimal_pair(pair<<shift,shift),want)
        self.assertEqual(STATUS['TEST_FINISHED'],10);self.assertEqual(RESULT['OKAY'],10)
    def test_decimal_pair_domains_reject_bool_and_outside_byte(self):
        for value,shift in [(True,0),(-1,0),(256,0),(0,True),(0,1),(0,8)]:
            with self.assertRaises(ValueError):decimal_pair(value,shift)
    def test_all_packed_byte_values_keep_each_axis(self):
        for packed in range(256):
            r=source_business_body(bytes([0,1,packed,10,11,100]))
            self.assertEqual(r['sourceTestStatus']['rawTwoBits'],packed&3)
            for axis,shift in [('pitch',2),('roll',4),('yaw',6)]:
                self.assertEqual(r['sourceResults'][axis]['rawTwoBits'],(packed>>shift)&3)
                self.assertEqual(r['sourceResults'][axis]['sourceDecimalValue'],int(format((packed>>shift)&3,'02b')))
            self.assertEqual(r['rawAdvice'],{'pitch':10,'roll':11,'yaw':100})
    def test_short_source_guard_does_not_make_short_body_valid(self):
        for length in range(6):
            with self.assertRaises(ValueError):source_business_body(bytes(length))
    def test_body_kind_and_tail_are_preserved(self):
        r=source_business_body(bytearray.fromhex('0001ff00ff80aabb'))
        self.assertEqual(r['trailingHex'],'aabb');self.assertEqual(r['sourceTestStatus']['sourceName'],'TEST_ERROR');self.assertEqual(r['rawAdvice']['roll'],255)
        self.assertFalse(r['targetDeviceVerified']);self.assertFalse(r['physicalCompletionVerified'])
        with self.assertRaises(ValueError):source_business_body([0]*6)
    def test_unknown_type_does_not_invent_source_singleton_values(self):
        for kind in range(1,256):
            r=source_business_body(bytes([kind,1,255,1,2,3]));self.assertEqual(r['rawType'],kind);self.assertFalse(r['sourceTypeRecognized']);self.assertIsNone(r['sourceTestStatus']);self.assertIsNone(r['sourceResults']);self.assertIsNone(r['rawAdvice'])
    def test_length_byte_is_not_silently_enforced_or_rewritten(self):
        for length in range(256):
            r=source_business_body(bytes([0,length,0,0,0,0]));self.assertEqual(r['rawLengthByte'],length);self.assertFalse(r['lengthByteValidatedBySource'])
    def test_invoke_owner_not_argument_or_return_type(self):
        self.assertEqual(invoked_owner('v0, '+SET+'->start(Ldji/midware/interfaces/DJIDataCallBack;)V'),(SET,'start'))
        self.assertEqual(invoked_owner('v0, Lcaller;->accept('+PUSH+')V'),('Lcaller;','accept'))
        self.assertEqual(invoked_owner('Lcaller;->get()'+PUSH),('Lcaller;','get'))
        self.assertIsNone(invoked_owner('v0, '+PUSH))
    def test_preflight_rejects_wrong_apk_and_each_bank_before_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);apk=d/'a';apk.write_bytes(b'fixture');pin=hashlib.sha256(b'bank').hexdigest()
            with self.assertRaisesRegex(ValueError,'APK hash'):trace(apk,d)
            for bad in BANKS:
                for bank in BANKS:(d/('business-%02d-code-restored.dex'%bank)).write_bytes(b'bad' if bank==bad else b'bank')
                with patch('ronin_balance_adjust.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()),patch('ronin_balance_adjust.BANKS',{b:pin for b in BANKS}):
                    with self.assertRaisesRegex(ValueError,'bank hash'):trace(apk,d)
    def test_committed_evidence_keeps_sdk_and_hardware_gates(self):
        p=Path(__file__).resolve().parents[2]/'protocol/research/ronin-balance-adjust-evidence.json'
        r=json.loads(p.read_text())
        self.assertEqual(r['commandEnumArguments'][2],64);self.assertEqual(r['commandEnumArguments'][-1],PUSH)
        for key in ['appCodeExecuted','liveUiExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded','hg724EntryEstablished']:self.assertFalse(r[key])
        self.assertFalse(r['sourceRequest']['sendEnabledInSdk']);self.assertFalse(r['sourceUi']['detachSendsStop']);self.assertEqual(r['sourceUi']['timerMs'],20000);self.assertTrue(r['sourceReceive']['bitPairsParsedAsDecimalStrings'])
