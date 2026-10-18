import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from ronin_subscription_init import captured_channels,trace,BANKS
class SubscriptionInitTests(unittest.TestCase):
 def rows(self):return json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-subscription-catalog.json').read_text())['registrations']
 def test_explicit_channels_independent_of_metadata(self):
  rows=self.rows();captured=captured_channels(rows,set())
  for row in rows:
   self.assertEqual(captured[row['key']],0 if row['channelSource']=='resource-if-present' else row['channel'])
 def test_complete_metadata_uses_pinned_channels(self):
  rows=self.rows();names={r['parameterName'] for r in rows if r['channelSource']=='resource-if-present'}
  self.assertEqual(captured_channels(rows,names),{r['key']:r['channel'] for r in rows})
 def test_partial_publication_is_per_name_and_capture_is_not_live(self):
  rows=self.rows();conditional=[r for r in rows if r['channelSource']=='resource-if-present'];name=conditional[0]['parameterName'];available={name};old=captured_channels(rows,available)
  for r in conditional:self.assertEqual(old[r['key']],r['channel'] if r['parameterName']==name else 0)
  available.update(r['parameterName'] for r in conditional)
  self.assertNotEqual(old,captured_channels(rows,available));self.assertEqual(old,captured_channels(rows,{name}))
 def test_explicit_metadata_set_required(self):
  for v in (None,[],{},True,{'name',1}):
   with self.assertRaises(ValueError):captured_channels(self.rows(),v)
 def test_wrong_apk_rejected_before_parser(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'apk';p.write_bytes(b'wrong')
   with self.assertRaisesRegex(ValueError,'APK hash mismatch'):trace(p,Path(tmp))
 def test_every_bank_prechecked_before_parser(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'apk';p.write_bytes(b'fixture');pin=hashlib.sha256(b'bank').hexdigest()
   for bad in BANKS:
    for bank in BANKS:(Path(tmp)/('business-%02d-code-restored.dex'%bank)).write_bytes(b'bad' if bank==bad else b'bank')
    with patch('ronin_subscription_init.APK_SHA256',hashlib.sha256(b'fixture').hexdigest()),patch('ronin_subscription_init.BANKS',{bank:pin for bank in BANKS}):
     with self.assertRaisesRegex(ValueError,'restored bank hash mismatch'):trace(p,Path(tmp))
 def test_evidence_preserves_initialization_and_scope_limits(self):
  e=json.loads((Path(__file__).resolve().parents[2]/'protocol/research/ronin-subscription-init-evidence.json').read_text())
  self.assertEqual(len(e['methods']),13);self.assertEqual(len(e['directCapturedIdWriters']),3)
  for k in ('appCodeExecuted','threadsStarted','targetDeviceVerified','wholeProtocolRecovered','runtimeInitializationOrderObserved'):self.assertIs(e[k],False)
  self.assertIs(e['sourceFacts']['completionBeforeBaseEnumInitializationProven'],False);self.assertIs(e['scope']['reflectionOrOtherClassLoadersRuledOut'],False)
