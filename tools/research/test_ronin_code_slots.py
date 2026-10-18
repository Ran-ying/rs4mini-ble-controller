import copy,json,struct,tempfile,unittest
from pathlib import Path
from ronin_code_slots import audit_bank,audit_apk,require_disjoint,table_damage,PREFIX

class CodeSlotTests(unittest.TestCase):
    def fixture(self):
        image=bytearray(0x20500);method_off=0x20080;class_off=0x20100;data=0x20200;code=0x20300
        items={0:(1,0),1:(1,112),2:(1,116),3:(1,120),4:(0,132),5:(1,method_off),6:(1,class_off),0x2000:(1,data),0x2001:(1,code),0x2002:(1,0x20400)}
        struct.pack_into('<HHI',image,method_off,0,0,0);struct.pack_into('<I',image,class_off,0);struct.pack_into('<I',image,class_off+24,data)
        encoded=[];n=code
        while True:
            b=n&127;n>>=7;encoded.append(b|(128 if n else 0))
            if not n:break
        image[data:data+6+len(encoded)]=bytes([0,0,1,0,0,1]+encoded)
        body=struct.pack('<4H2I',1,0,0,0,0,1)+b'\x0e\x00';image[code:code+len(body)]=body
        bank=dict(originalSize=len(image),rows=[dict(slot=data+6,size=len(body),dataOffset=0,code=body)])
        return image,items,bank
    def test_numeric_slot_ownership_and_footprint_without_metadata_repairs(self):
        image,items,bank=self.fixture();before=bytes(image);r,records=audit_bank(image,items,bank)
        self.assertEqual(bytes(image),before);self.assertEqual(r['matchedBackupCodeItems'],1);self.assertEqual(records[0]['methodIndex'],0);self.assertEqual(records[0]['codeOffset'],0x20300)
        self.assertTrue(r['allBackupSlotsMatched']);self.assertTrue(r['methodOwnerIndicesConsistent']);self.assertFalse(r['parseableDexProduced'])
    def test_required_tables_cannot_overlap_damaged_prefix(self):
        for kind in [5,6]:
            image,items,bank=self.fixture();items[kind]=(1,PREFIX-1)
            with self.assertRaisesRegex(ValueError,'metadata intersects'):audit_bank(image,items,bank)
    def test_class_data_must_be_in_intact_mapped_region(self):
        for offset in [PREFIX-1,0x20300]:
            image,items,bank=self.fixture();struct.pack_into('<I',image,items[6][1]+24,offset)
            with self.assertRaisesRegex(ValueError,'class data outside'):audit_bank(image,items,bank)
    def test_method_owner_must_match_its_class_definition(self):
        image,items,bank=self.fixture();items[2]=(2,116);struct.pack_into('<H',image,items[5][1],1)
        with self.assertRaisesRegex(ValueError,'owner index mismatch'):audit_bank(image,items,bank)
    def test_numeric_method_indices_respect_name_and_prototype_counts(self):
        for field,fmt,offset in [('name','<I',4),('proto','<H',2)]:
            image,items,bank=self.fixture();struct.pack_into(fmt,image,items[5][1]+offset,1)
            with self.assertRaisesRegex(ValueError,'outside declared table'):audit_bank(image,items,bank)
    def test_backup_slot_must_be_exact_and_unique(self):
        image,items,bank=self.fixture();bank['rows'][0]['slot']+=1
        with self.assertRaisesRegex(ValueError,'unique exact'):audit_bank(image,items,bank)
        image,items,bank=self.fixture();bank['rows']*=2
        with self.assertRaisesRegex(ValueError,'unique exact'):audit_bank(image,items,bank)
    def test_code_size_destination_and_units_are_bounded(self):
        image,items,bank=self.fixture();struct.pack_into('<I',image,0x20300+12,2)
        with self.assertRaises(ValueError):audit_bank(image,items,bank)
        image,items,bank=self.fixture();bank['rows'][0]['size']+=1
        with self.assertRaises(ValueError):audit_bank(image,items,bank)
        image,items,bank=self.fixture();image[0x20206:0x20209]=bytes([0x81,0x86,8])
        with self.assertRaises(ValueError):audit_bank(image,items,bank)
    def test_overlaps_reject_but_touching_regions_are_valid(self):
        require_disjoint([(4,8),(0,4)])
        for spans in [[(4,8),(0,5)],[(4,8),(4,8)]]:
            with self.assertRaisesRegex(ValueError,'overlapping'):require_disjoint(spans)
    def test_partial_entry_damage_rounds_up_without_claiming_recovery(self):
        _,items,_=self.fixture();items[4]=(10,PREFIX-4)
        rows={r['mapType']:r for r in table_damage(items)}
        self.assertEqual(rows[4]['bytesInsideObservedDamagedPrefix'],4);self.assertEqual(rows[4]['entriesIntersectingPrefix'],1);self.assertEqual(rows[5]['entriesIntersectingPrefix'],0)
    def test_wrong_apk_rejected_without_output_or_zip_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a';p.write_bytes(b'other app')
            with self.assertRaisesRegex(ValueError,'APK hash'):audit_apk(p)
    def test_slot_digest_is_deterministic_and_does_not_imply_named_identity(self):
        image,items,bank=self.fixture();a,rows=audit_bank(image,items,bank);b,_=audit_bank(bytes(image),copy.deepcopy(items),copy.deepcopy(bank));self.assertEqual(a,b)
        self.assertEqual(len(a['slotRecordSha256']),64)
        for flag in ['namedMetadataRestored','stringOrderIndependentlyCorroborated','typeIdentityRecovered','prototypeIdentityRecovered','parseableDexProduced']:self.assertFalse(a[flag])
        self.assertNotIn('className',rows[0]);self.assertNotIn('methodName',rows[0])
    def test_committed_summary_keeps_unresolved_banks_and_hardware_gates(self):
        p=Path(__file__).resolve().parents[2]/'protocol/research/ronin-code-slots-evidence.json';r=json.loads(p.read_text())
        self.assertEqual([b['segment'] for b in r['banks']],[1,7]);self.assertEqual([b['matchedBackupCodeItems'] for b in r['banks']],[2623,514]);self.assertEqual(r['additionalBackupSlotsAudited'],3137)
        self.assertEqual(r['namedMetadataStillUnresolvedBanks'],[1,7])
        for flag in ['appCodeExecuted','liveUiExecuted','targetDeviceVerified','wholeAppRecovered','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded','existingSixRestoredDexViewsChanged']:self.assertFalse(r[flag])
        for b in r['banks']:
            self.assertTrue(b['allBackupSlotsMatched']);self.assertFalse(b['namedMetadataRestored']);self.assertFalse(b['parseableDexProduced'])
