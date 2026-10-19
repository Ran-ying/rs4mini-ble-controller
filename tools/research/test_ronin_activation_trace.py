import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_activation_trace import nullable_literal_enums,constructor_types,enum_literal_prefix,literal_switch_cases,source_type_value,source_set_layout,trace,PREFIX_BANKS,ROOT
OWNER='Lfixture/Enum;'
class ActivationTraceTests(unittest.TestCase):
    def ops(self,label='ActiveStatus',last_type='Ljava/lang/Class;',last=None):
        rows=[('new-instance','v0, '+OWNER),('const-string','v1, '+label),('const/16','v2, 20'),('const/16','v3, 50'),('const/4','v4, 0'),('const/4','v5, 1')]
        rows.extend(last or [('const/4','v6, 0')]);rows.append(('invoke-direct/range','v0 ... v6, '+OWNER+'-><init>(Ljava/lang/String; I I Z Z '+last_type+')V'));return rows
    def test_explicit_reference_zero_is_null_with_index(self):
        r=nullable_literal_enums(self.ops(),OWNER)['ActiveStatus'];self.assertEqual(r['arguments'],['ActiveStatus',20,50,0,1,None]);self.assertEqual(r['explicitNullArgumentIndexes'],[5]);self.assertEqual(r['unresolvedReferenceArgumentIndexes'],[])
    def test_unknown_reference_is_never_implicitly_null(self):
        with self.assertRaisesRegex(ValueError,'unresolved'):nullable_literal_enums(self.ops(last=[('move-result-object','v6')]),OWNER)
    def test_zero_primitive_remains_int_not_null(self):
        r=nullable_literal_enums(self.ops(last_type='I'),OWNER)['ActiveStatus'];self.assertEqual(r['arguments'][-1],0);self.assertEqual(r['explicitNullArgumentIndexes'],[]);self.assertIs(type(r['arguments'][3]),int)
    def test_literal_class_is_preserved(self):
        r=nullable_literal_enums(self.ops(last=[('const-class','v6, Lfixture/Model;')]),OWNER)['ActiveStatus'];self.assertEqual(r['arguments'][-1],'Lfixture/Model;');self.assertEqual(r['explicitNullArgumentIndexes'],[])
    def test_move_alias_does_not_guess_unknown(self):
        for op in ['move-object','move-object/from16','move-object/16']:
            r=nullable_literal_enums(self.ops(last=[('const/4','v7, 0'),(op,'v6, v7')]),OWNER);self.assertEqual(r['ActiveStatus']['explicitNullArgumentIndexes'],[5])
    def test_destroyed_values_and_conditional_initializers_reject(self):
        for rows in [self.ops(last=[('const/4','v6, 0'),('sget-object','v6, Lx;->zero Ljava/lang/Class;')]),[('goto','+01h')]+self.ops(),self.ops(last=[('const/4','v6, -1')])]:
            with self.assertRaises(ValueError):nullable_literal_enums(rows,OWNER)
    def test_constructor_types_are_bounded_not_arbitrary_descriptor_cleanup(self):
        self.assertEqual(constructor_types('(Ljava/lang/String; I Z Lx/Base;)V'),['Ljava/lang/String;','I','Z','Lx/Base;'])
        for desc in ['(Ljava/lang/ Str ing;)V','(J)V','([I)V','(I)I']:
            with self.assertRaises(ValueError):constructor_types(desc)
    def test_selected_scope_does_not_claim_other_unresolved_enum(self):
        rows=self.ops('Other',last_type='Lx/Base;',last=[('move-result-object','v6')])+self.ops()
        r=nullable_literal_enums(rows,OWNER,selected={'ActiveStatus'});self.assertEqual(list(r),['ActiveStatus'])
        with self.assertRaises(ValueError):nullable_literal_enums(rows,OWNER)
        footer=[('invoke-static',OWNER+'->$values()['+OWNER),('goto','+01h')]
        self.assertEqual(enum_literal_prefix(self.ops()+footer,OWNER),self.ops())
        with self.assertRaises(ValueError):enum_literal_prefix(self.ops()+footer+self.ops('Again'),OWNER)
    def test_opaque_other_reference_is_explicit_not_null_or_class(self):
        r=nullable_literal_enums(self.ops(last_type='Lx/Base;',last=[('move-result-object','v6')]),OWNER,allow_opaque_references=True)['ActiveStatus'];self.assertEqual(r['arguments'][-1],{'unresolvedReferenceType':'Lx/Base;'});self.assertEqual(r['unresolvedReferenceArgumentIndexes'],[5]);self.assertEqual(r['explicitNullArgumentIndexes'],[])
        for typ in ['I','Ljava/lang/Class;']:
            with self.assertRaises(ValueError):nullable_literal_enums(self.ops(last_type=typ,last=[('move-result-object','v6')]),OWNER,allow_opaque_references=True)
    def test_version_names_and_source_values_are_not_ordinals(self):
        enum=ROOT[:-1]+'$DJIActiveVersion;'
        ops=[('sget-object','v1, '+enum+'->Ver1_1 '+enum),('invoke-virtual','v1, '+enum+'->ordinal()I'),('move-result','v1'),('const/4','v2, 2'),('aput','v2, v0, v1')]
        self.assertEqual(literal_switch_cases(ops,enum),{'Ver1_1':2})
        with self.assertRaises(ValueError):literal_switch_cases(ops[:-1]+[('aput','v2, v0, v3')],enum)
        self.assertEqual(source_type_value('GET','Ver1_1'),17);self.assertEqual(source_type_value('SET','Ver1_3'),18);self.assertEqual(source_type_value('SET','Ver13'),2);self.assertEqual(source_type_value('GetVer','Ver1_1'),0);self.assertEqual(source_type_value('SetWebData','Ver1_0'),6);self.assertEqual(source_type_value('SetWebData','Ver1_1'),55)
    def test_layout_retains_allocation_copy_limit_and_zero_tail(self):
        for n in [0,1,10,16,17,255,256]:
            old=source_set_layout('Ver1_0',n);new=source_set_layout('Ver1_1',n)
            self.assertEqual(old['allocatedBytes'],19);self.assertEqual(old['snOffset'],9);self.assertEqual(old['copiedSnBytes'],min(n,10));self.assertIsNone(old['snLengthByteOffset'])
            self.assertEqual(new['allocatedBytes'],n+10);self.assertEqual(new['copiedSnBytes'],min(n,16));self.assertEqual(new['trailingZeroBytes'],n-min(n,16));self.assertFalse(new['targetDeviceVerified'])
    def test_helpers_require_explicit_names_and_java_safe_length(self):
        for v,n in [('missing',0),('Ver1_1',True),('Ver1_1',-1),('Ver1_1',2147483638),(None,0)]:
            with self.assertRaises(ValueError):source_set_layout(v,n)
        with self.assertRaises(ValueError):source_type_value('SET',1)
        with self.assertRaises(ValueError):source_type_value('missing','Ver1_1')
    def test_wrong_apk_rejects_before_loading_banks(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);p=d/'a';p.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'APK hash'):trace(p,d)
    def test_each_eight_bank_hash_checked_before_optional_parser(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);p=d/'a';p.write_bytes(b'apk');pin=hashlib.sha256(b'bank').hexdigest()
            for bad in PREFIX_BANKS:
                for b in PREFIX_BANKS:(d/('business-%02d-prefix-code-restored.dex'%b)).write_bytes(b'bad' if b==bad else b'bank')
                with patch('ronin_activation_trace.APK_SHA256',hashlib.sha256(b'apk').hexdigest()),patch('ronin_activation_trace.PREFIX_BANKS',{b:pin for b in PREFIX_BANKS}):
                    with self.assertRaisesRegex(ValueError,'bank hash'):trace(p,d)
    def test_evidence_keeps_generic_candidate_and_sdk_gates(self):
        r=json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-activation-evidence.json').read_text());self.assertEqual(r['command']['commandSet'],0);self.assertEqual(r['command']['commandId'],50);self.assertEqual(r['command']['enumBinding']['arguments'][1],20);self.assertEqual(r['commonEnumScope'],['ActiveStatus']);self.assertEqual(r['sourceGimbalSingletonInitialVersion'],'Ver1_1')
        for flag in ['appCodeExecuted','liveUiExecuted','targetDeviceVerified','wholeProtocolRecovered','researchToolProvidesSdkInterface','sdkSendAdded','sdkReceiveAdded','hg724EntryEstablished','bleRouteVerified','activationPersistenceVerified','actualSessionVersionVerified','networkVsDeviceWorkflowFullyAudited']:self.assertFalse(r[flag])
    def test_business_read_fields_do_not_become_verified_wire_offsets(self):
        r=json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-activation-evidence.json').read_text())['sourceResponse'];self.assertEqual(r['businessActiveBit'],{'offset':0,'width':1,'mask':1});self.assertEqual(r['yearOffset'],1);self.assertEqual(r['snOther']['lengthOffset'],8);self.assertFalse(r['wireOffsetsIndependentlyVerified']);self.assertFalse(r['ackAndPushBusinessBodiesUnified'])
