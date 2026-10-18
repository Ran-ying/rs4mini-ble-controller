import hashlib,json,struct,tempfile,unittest,zlib
from pathlib import Path
from unittest.mock import patch
from ronin_prefix_restore import decrypt_ecb,round_keys,check_plain_header,native_material,restore_apk,inspect_new_banks,PREFIX_BYTES,PREFIX_BANKS
SBOX=bytes.fromhex('d690e9fecce13db716b614c228fb2c052b679a762abe04c3aa441326498606999c4250f491ef987a33540b43edcfac62e4b31ca9c908e89580df94fa758f3fa64707a7fcf37317ba83593c19e6854fa8686b81b27164da8bf8eb0f4b70569d351e240e5e6358d1a225227c3b01217887d40046579fd327524c3602e7a0c4c89eeabf8ad240c738b5a3f7f2cef96115a1e0ae5da49b341a55ad933230f58cb1e31df6e22e8266ca60c02923ab0d534e6fd5db3745defd8e2f03ff6a726d6c5b518d1baf92bbddbc7f11d95c411f105ad80ac13188a5cd7bbd2d74d012b8e5b4b08969974a0c96777e65b9f109c56ec68418f07dec3adc4d2079ee5f3ed7cb3948')
CK=tuple(sum((((4*i+j)*7)&255)<<(24-8*j) for j in range(4)) for i in range(32))
KEY=bytes.fromhex('0123456789abcdeffedcba9876543210');CIPHER=bytes.fromhex('681edf34d206965e86b3e94f536e4246')
class PrefixRestoreTests(unittest.TestCase):
    def fixture(self):
        b=bytearray(PREFIX_BYTES+1024);original=PREFIX_BYTES+512;data=PREFIX_BYTES+128
        b[:8]=b'dex\n039\0';struct.pack_into('<3I',b,32,len(b),112,0x12345678);struct.pack_into('<I',b,52,data)
        items={1:(1,112),2:(1,116),3:(1,120),4:(0,132),5:(1,160),6:(1,168),0x1000:(1,data)}
        for kind,off in [(1,56),(2,64),(3,72),(4,80),(5,88),(6,96)]:struct.pack_into('<II',b,off,*items[kind])
        struct.pack_into('<II',b,104,original-data,data);b[12:32]=b'Z'*20;struct.pack_into('<I',b,8,zlib.adler32(b[12:])&0xffffffff)
        return b,dict(mapOffset=data,items=items),dict(originalSize=original)
    def evidence(self,name='ronin-prefix-restoration-evidence.json'):
        return json.loads((Path(__file__).resolve().parents[2]/'protocol/research'/name).read_text())
    def test_sm4_known_answer_vector(self):
        self.assertEqual(decrypt_ecb(CIPHER,KEY,SBOX,CK),KEY)
    def test_ecb_whole_blocks_are_independent(self):
        self.assertEqual(decrypt_ecb(CIPHER*3,KEY,SBOX,CK),KEY*3)
    def test_ciphertext_domain_has_no_padding_or_empty_default(self):
        for value in [b'',b'x',bytes(17),bytearray(16),None]:
            with self.assertRaises(ValueError):decrypt_ecb(value,KEY,SBOX,CK)
    def test_key_table_dimensions_reject_partial_or_nonpermutation(self):
        for key,sbox,ck in [(KEY[:-1],SBOX,CK),(KEY,SBOX[:-1],CK),(KEY,bytes(256),CK),(KEY,SBOX,CK[:-1])]:
            with self.assertRaises(ValueError):round_keys(key,sbox,ck)
    def test_round_key_known_answers(self):
        rk=round_keys(KEY,SBOX,CK);self.assertEqual(len(rk),32);self.assertEqual(rk[0],0xf12186f9);self.assertEqual(rk[-1],0x9124a012)
    def test_header_accepts_source_adler_but_does_not_launder_sha1(self):
        b,m,bank=self.fixture();before=bytes(b);result,checks=check_plain_header(b,m,bank);self.assertEqual(result,before);self.assertEqual(bytes(b),before);self.assertTrue(checks['sourceProtectedContainerAdler32Matched']);self.assertFalse(checks['sourceHeaderSha1MatchesProtectedContainer'])
    def test_wrong_magic_header_size_endian_and_container_bounds_reject(self):
        for off,fmt,value in [(32,'<I',PREFIX_BYTES-1),(32,'<I',PREFIX_BYTES+1025),(36,'<I',0),(40,'<I',0)]:
            b,m,bank=self.fixture();struct.pack_into(fmt,b,off,value)
            with self.assertRaises(ValueError):check_plain_header(b,m,bank)
        b,m,bank=self.fixture();b[0]=0
        with self.assertRaisesRegex(ValueError,'magic'):check_plain_header(b,m,bank)
    def test_id_tables_and_map_pointer_must_match_independent_map(self):
        for off in [52,56,64,72,80,88,96]:
            b,m,bank=self.fixture();struct.pack_into('<I',b,off,0xffffffff)
            with self.assertRaisesRegex(ValueError,'map'):check_plain_header(b,m,bank)
    def test_original_data_bounds_are_distinct_from_container_size(self):
        b,m,bank=self.fixture();struct.pack_into('<I',b,104,len(b))
        with self.assertRaisesRegex(ValueError,'data bounds'):check_plain_header(b,m,bank)
    def test_any_protected_container_corruption_rejects_before_normalization(self):
        b,m,bank=self.fixture();b[-1]^=1
        with self.assertRaisesRegex(ValueError,'Adler32'):check_plain_header(b,m,bank)
    def test_native_material_is_pinned_before_transform(self):
        with self.assertRaisesRegex(ValueError,'library hash'):native_material(b'other native file')
    def test_wrong_apk_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);p=d/'a';p.write_bytes(b'other app');out=d/'out'
            with self.assertRaisesRegex(ValueError,'APK hash'):restore_apk(p,out,d)
            self.assertFalse(out.exists())
    def test_optional_inspector_checks_both_hashes_before_importing_parser(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)
            for b in [1,7]:(d/('business-%02d-prefix-code-restored.dex'%b)).write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'DEX hash'):inspect_new_banks(d)
            pins={1:hashlib.sha256(b'bad').hexdigest(),7:'wrong'}
            with patch('ronin_prefix_restore.PREFIX_BANKS',pins):
                with self.assertRaisesRegex(ValueError,'DEX hash'):inspect_new_banks(d)
    def test_eight_view_summary_keeps_sdk_and_full_app_gates_false(self):
        r=self.evidence();self.assertEqual(r['namedDexViewsRecovered'],8);self.assertEqual(r['restoredBackupCodeItems'],52679);self.assertEqual([b['derivedSha256'] for b in r['banks']],list(PREFIX_BANKS.values()))
        for flag in ['appCodeExecuted','liveUiExecuted','nativeLibraryExecuted','targetDeviceVerified','wholeAppRecovered','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded','previousSixFilesModified','legacyCallerEvidenceScopeAutomaticallyExpanded']:self.assertFalse(r[flag])
    def test_source_checksums_and_legacy_semantic_bytes_are_separate(self):
        r=self.evidence()
        for b in r['banks']:
            self.assertTrue(b['sourceProtectedContainerAdler32Matched']);self.assertFalse(b['sourceHeaderSha1MatchesProtectedContainer']);self.assertTrue(b['normalizedViewChecksumsRegenerated'])
            if b['segment'] in [1,7]:self.assertIsNone(b['legacySemanticBytes112ToOriginalSizeMatch'])
            else:self.assertTrue(b['legacySemanticBytes112ToOriginalSizeMatch'])
        v=self.evidence('ronin-prefix-independent-validation.json');self.assertTrue(v['allPrefixesMatched']);self.assertEqual(v['totalBytesCompared'],8*PREFIX_BYTES)
        self.assertEqual([b['decryptedPrefixSha256'] for b in v['banks']],[b['decryptedPrefixSha256'] for b in r['banks']])
    def test_new_caller_scan_is_supplement_not_target_support(self):
        r=self.evidence('ronin-prefix-new-callers.json');self.assertEqual([b['classDefinitions'] for b in r['banks']],[2297,641]);self.assertEqual([b['declaredMethods'] for b in r['banks']],[12143,3240]);self.assertEqual([b['gimbalDirectInvocations'] for b in r['banks']],[60,0]);self.assertEqual(len(r['directCallerMethods']),19)
        for flag in ['appCodeExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded','modelPathsVerified','cameraApisAdded','activationCommandsAdded']:self.assertFalse(r[flag])
