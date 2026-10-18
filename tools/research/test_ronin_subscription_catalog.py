import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_subscription_catalog import (resolve_base,registrations,switch_assignments,snapshot,registers,trace,IMPL,OWNER,TYPE,CMD,COMPONENT,SWITCH,MOTOR)
class SubscriptionCatalogTests(unittest.TestCase):
 def row(self,key='K',channel=41,source='resource-if-present',condition=None):return dict(key=key,commandId=16,channel=channel,channelSource=source,sourceCondition=condition,missingMetadataChannel=0 if source=='resource-if-present' else None)
 def ins(self,ops):return [dict(op=o,text=t,offset=i*2) for i,(o,t) in enumerate(ops)]
 def catalog(self):return json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-subscription-catalog.json').read_text())
 def test_explicit_id_not_enum_ordinal(self):
  r=resolve_base(dict(arguments=['X',71,3,'name']),[]);self.assertEqual((r['commandId'],r['channel']),(16,3));self.assertIsNone(r['missingMetadataChannel'])
 def test_explicit_motor_namespace_is_separate(self):
  r=resolve_base(dict(arguments=['X',1,0,'name',MOTOR]),[]);self.assertEqual((r['commandId'],r['channel']),(50,0))
 def test_resource_candidate_and_java_zero_fallback_are_distinct(self):
  r=resolve_base(dict(arguments=['X',1,'name']),[dict(name='name',index=41,size=1,typeID=0,minValue=0,maxValue=100)]);self.assertEqual(r['channel'],41);self.assertEqual(r['missingMetadataChannel'],0);self.assertEqual(r['channelSource'],'resource-if-present')
 def test_unknown_resource_or_class_not_guessed(self):
  with self.assertRaises(ValueError):resolve_base(dict(arguments=['X',1,'missing']),[])
  with self.assertRaises(ValueError):resolve_base(dict(arguments=['X',1,0,'name','LUnknown;']),[])
 def test_metadata_case_required_and_empty_is_not_stop(self):
  rows=[self.row()]
  with self.assertRaises(ValueError):snapshot(['K'],rows)
  self.assertEqual(snapshot(['K'],rows,metadata_case='db-present')['bodyHex'],'1029000000000002')
  self.assertEqual(snapshot(['K'],rows,metadata_case='missing')['bodyHex'],'100001')
  with self.assertRaises(ValueError):snapshot([],rows)
 def test_support_case_must_be_explicit_true(self):
  rows=[self.row(source='explicit-base',condition='isSupportStateSince4Gen')]
  for v in (None,False,1):
   with self.assertRaises(ValueError):snapshot(['K'],rows,state_since4gen=v)
  self.assertEqual(snapshot(['K'],rows,state_since4gen=True)['bodyHex'],'1029000000000002')
 def test_duplicate_names_and_shared_channels_deduplicate_bits(self):
  rows=[self.row('A',21,'explicit-base'),self.row('B',21,'explicit-base')]
  r=snapshot(['B','A','B'],rows);self.assertEqual(r['selectedKeys'],['A','B']);self.assertEqual(r['groups'],[dict(commandId=16,channels=[21])]);self.assertEqual(r['bodyHex'],'1015000020');self.assertFalse(r['remoteStopVerified'])
 def test_invalid_name_case_or_types_rejected(self):
  for keys in (None,[],[True],['unknown']):
   with self.assertRaises(ValueError):snapshot(keys,[self.row()])
  with self.assertRaises(ValueError):snapshot(['K'],[self.row()],metadata_case='guess')
 def test_three_source_groups_and_alias_vector(self):
  rows=self.catalog()['registrations']
  self.assertEqual(snapshot(['PeripheralPosYaw','UserProfile','PitchMotorControlStiffness'],rows)['bodyHex'],'10000132000166240000000010')
  self.assertEqual(snapshot(['PeripheralGyroOutYaw','PeripheralGyroAccePitch'],rows)['bodyHex'],'6615000020')
 def test_whole_named_catalog_needs_cases_not_152_capability_claim(self):
  catalog=self.catalog();rows=catalog['registrations'];r=snapshot([x['key'] for x in rows],rows,metadata_case='db-present',state_since4gen=True)
  self.assertEqual(len(r['selectedKeys']),152);self.assertEqual(len(bytes.fromhex(r['bodyHex'])),36);self.assertEqual(sum(len(g['channels']) for g in r['groups']),121)
  missing=snapshot([x['key'] for x in rows],rows,metadata_case='missing',state_since4gen=True);self.assertEqual(sum(len(g['channels']) for g in missing['groups']),106)
  unconditional=snapshot([x['key'] for x in rows if not x['sourceCondition']],rows,metadata_case='db-present',state_since4gen=False);self.assertEqual(len(unconditional['selectedKeys']),150)
 def literals(self):return [('const-string/jumbo','v0, K'),('sget-object','v1, '+OWNER+'->X '+OWNER),('invoke-direct','v9, v0, v1, '+IMPL+'->put(Ljava/lang/String; '+OWNER+')V')]
 def test_registration_matches_exact_named_base_reference(self):
  rows=registrations(self.ins(self.literals()),{'X':dict(arguments=['X',7,3,'name'])},{},{},[]);self.assertEqual((rows[0]['key'],rows[0]['channel']),('K',3))
 def test_duplicate_registration_and_unresolved_return_rejected(self):
  with self.assertRaises(ValueError):registrations(self.ins(self.literals()*2),{'X':dict(arguments=['X',7,3,'name'])},{},{},[])
  wrong=self.literals();wrong[1]=('move-result-object','v1')
  with self.assertRaises(ValueError):registrations(self.ins(wrong),{}, {},{},[])
 def test_unrecognized_constructor_branch_is_not_silently_walked(self):
  with self.assertRaises(ValueError):registrations([dict(op='if-eqz',text='v0, +ah',offset=0,target=20)],{},{},{},[])
 def test_supported_if_interval_does_not_leak_to_next_registration(self):
  ops=self.ins([('invoke-direct','v9, '+IMPL+'->isSupportStateSince4Gen()Z'),('move-result','v0'),('if-eqz','v0, +ah')]+self.literals()+[('const-string/jumbo','v0, Other')]+self.literals()[1:]);ops[2]['target']=12
  r=registrations(ops,{'X':dict(arguments=['X',7,3,'name'])},{},{},[]);self.assertEqual([x['sourceCondition'] for x in r],['isSupportStateSince4Gen',None])
 def test_invoke_range_is_resolved_not_ordinal_inferred(self):
  self.assertEqual(registers('v1 ... v4, '+IMPL+'->put(Ljava/lang/String; I I)V',IMPL),['v1','v2','v3','v4'])
 def switch_ops(self):
  return [('new-array','v0, v3, [I'),('sput-object','v0, '+SWITCH+'->$SwitchMap$dji$midware$component$DJIComponentManager$GimbalComponentType [I'),('sget-object','v1, '+COMPONENT+'->HG701 '+COMPONENT),('invoke-virtual','v1, '+COMPONENT+'->ordinal()I'),('move-result','v1'),('const/4','v2, 1'),('aput','v2, v0, v1')]
 def test_new_static_switch_array_and_enum_field_are_linked(self):
  self.assertEqual(switch_assignments(self.switch_ops()),{'HG701':1})
 def test_unknown_and_duplicate_switch_assignments_rejected(self):
  with self.assertRaises(ValueError):switch_assignments([('aput','v2, v0, v1')])
  with self.assertRaises(ValueError):switch_assignments(self.switch_ops()*2)
 def test_apk_and_bank_hash_checks_precede_parser(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'apk';p.write_bytes(b'bad')
   with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(d))
   (Path(d)/'business-05-code-restored.dex').write_bytes(b'bad')
   with patch('ronin_subscription_catalog.APK_SHA256',hashlib.sha256(b'bad').hexdigest()):
    with self.assertRaisesRegex(ValueError,'bank hash mismatch'):trace(p,Path(d))

 def test_unsupported_register_definition_cannot_reuse_stale_key(self):
  ops=self.literals();ops.insert(1,('const-class','v0, LNotAString;'))
  with self.assertRaises(ValueError):registrations(self.ins(ops),{'X':dict(arguments=['X',7,3,'name'])},{},{},[])
