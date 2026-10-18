import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_balance_entry import source_route,model_literals,trace,BANKS,MODEL,NEEDS_TEST,SECOND,THIRD,FOURTH,FIFTH

class BalanceEntryTests(unittest.TestCase):
    def evidence(self):
        return json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-balance-entry-evidence.json').read_text())
    def test_hg724_explicit_selected_item_routes_to_video(self):
        r=source_route('HG724');self.assertFalse(r['needBalanceTest']);self.assertEqual(r['menuTarget'],'GimbalVideoAdjustRS3');self.assertEqual(r['videoTestButtonVisibility'],8)
    def test_legacy_test_route_is_a_specific_set(self):
        self.assertEqual(NEEDS_TEST,{'RONIN2','RONINS','RONINSC','HG720','HG702','HG710'})
        for name in NEEDS_TEST:
            r=source_route(name);self.assertTrue(r['needBalanceTest']);self.assertEqual(r['menuTarget'],'ConfigSettingBalanceTestHG701');self.assertEqual(r['videoTestButtonVisibility'],0)
    def test_other_generations_do_not_all_inherit_old_test_entry(self):
        for name in THIRD|FOURTH|FIFTH:
            self.assertEqual(source_route(name)['needBalanceTest'],name=='HG720')
    def test_forced_old_view_visibility_is_not_entry_reachability(self):
        self.assertEqual(source_route('HG724')['forcedOldCheckAdjustTextVisibility'],0)
        self.assertFalse(source_route('HG724')['needBalanceTest'])
        for name in ['RONIN2','RONINS','UNKNOWN']:self.assertEqual(source_route(name)['forcedOldCheckAdjustTextVisibility'],4)
    def test_explicit_model_required_not_index_or_boolean(self):
        for name in [None,True,0,103,[],{},'']:
            with self.assertRaises(ValueError):source_route(name)
        self.assertFalse(source_route('UNKNOWN')['needBalanceTest'])
    def test_cases_are_copied_and_never_claim_live_or_firmware_proof(self):
        r=source_route('HG724');r['menuTarget']='GimbalAdjustHG701';self.assertEqual(source_route('HG724')['menuTarget'],'GimbalVideoAdjustRS3')
        for flag in ['actualSelectedModelVerified','liveUiVerified','firmwareSupportVerified']:self.assertFalse(source_route('HG724')[flag])
    def test_model_literals_only_match_model_field_reads(self):
        rows=[('sget-object','v0, '+MODEL+'->HG724 '+MODEL),('const-string','v0, '+MODEL+'->RONINS '+MODEL),('sget-object','v0, Lother;->HG710 Lother;')]
        self.assertEqual(model_literals(rows),{'HG724'})
    def test_wrong_apk_rejects_before_bank_access(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);p=d/'a';p.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'APK hash'):trace(p,d)
    def test_every_bank_is_pinned_before_optional_parser(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);p=d/'a';p.write_bytes(b'apk');pin=hashlib.sha256(b'bank').hexdigest()
            for bad in BANKS:
                for bank in BANKS:(d/('business-%02d-code-restored.dex'%bank)).write_bytes(b'bad' if bank==bad else b'bank')
                with patch('ronin_balance_entry.APK_SHA256',hashlib.sha256(b'apk').hexdigest()),patch('ronin_balance_entry.BANKS',{bank:pin for bank in BANKS}):
                    with self.assertRaisesRegex(ValueError,'bank hash'):trace(p,d)
    def test_evidence_does_not_turn_menu_condition_into_command_support(self):
        r=self.evidence();self.assertEqual(len(r['methods']),30)
        for flag in ['appCodeExecuted','liveUiExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded','hg724Command40PathEstablished','hg724Command40UnsupportedProven']:self.assertFalse(r[flag])
        self.assertEqual(r['explicitHg724SelectedCase'],source_route('HG724'))
    def test_video_names_share_one_resource_not_adjust_view(self):
        r=self.evidence();self.assertEqual(len(r['layouts']),4);self.assertEqual(r['uniqueLayoutCount'],3)
        nav=r['navigation'];a=nav['GimbalVideoAdjustHG701'];b=nav['GimbalVideoAdjustRS3'];self.assertNotEqual(a['ordinal'],b['ordinal']);self.assertEqual(a['layoutId'],b['layoutId']);self.assertEqual(a['viewId'],b['viewId'])
        self.assertEqual(nav['GimbalAdjustHG701']['viewId'],-1)
        roots={x['viewName']:x['rootClass'] for x in r['layouts']};self.assertNotEqual(roots['GimbalAdjustHG701'],roots['GimbalVideoAdjustRS3'])
    def test_literal_references_do_not_become_direct_navigation(self):
        rows=self.evidence()['oldAdjustLiteralReferenceMethods']
        self.assertEqual({r['method'] for r in rows},{'$values','<clinit>','shouldRespondBackPress'})
        self.assertEqual(len(rows),3)
        self.assertTrue(all(ref['opcode'] in ('sget-object','sput-object') for r in rows for ref in r['references']))
