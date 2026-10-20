import asyncio,json,pathlib,unittest
import test_controller as fixtures
from test_app_commands import reply
from rs4mini_sdk.app_external_device import external_device_notification
VECTORS=json.loads((pathlib.Path(__file__).resolve().parents[2]/'node/test/fixtures/external-device.json').read_text())
def body():return bytes.fromhex(VECTORS[0]['bodyHex'])
def message(payload=None,flags=0):return dict(sender=4,receiver=2,commandSet=4,commandId=105,flags=flags,payload=body() if payload is None else payload)
class ExternalDeviceTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 def incoming(self,payload=None,flags=0,command=105,sequence=1):reply(self.client,dict(sequence=sequence,commandId=command),body() if payload is None else payload,lambda data:data.__setitem__(8,flags))
 async def test_shared_vectors_and_verification_flags(self):
  for v in VECTORS:
   r=external_device_notification(message(bytes.fromhex(v['bodyHex'])));self.assertEqual(r['records'],v['records']);self.assertEqual(r['bodyHex'],v['bodyHex'])
   for k,value in r.items():
    if k.endswith('Verified'):self.assertIs(value,False)
  s=external_device_notification(message())['records'][0]['speedControl'];self.assertEqual((s['sourcePitchSpeed'],s['sourceRollSpeed'],s['sourceYawSpeed']),(-32768,32767,0))
 async def test_unknown_source_and_missing_speeds_preserved(self):
  for n,known,raw in ((2,True,7),(3,False,255)):
   s=external_device_notification(message(bytes.fromhex(VECTORS[n]['bodyHex'])))['records'][0]['speedControl'];self.assertEqual(s['sourceControlType'],'Other');self.assertIs(s['sourceControlTypeKnown'],known);self.assertEqual(s['rawControlType'],raw)
  self.assertNotIn('speedControl',external_device_notification(message(bytes.fromhex('ff00')))['records'][0])
 async def test_malformed_and_wrong_envelope_reject(self):
  for payload in (b'',b'\2',bytes((2,6))+bytes(6),bytes((2,7))+bytes(6),bytes((9,128))+bytes(128),body()+b'\11',[]):self.assertIsNone(external_device_notification(message(payload)))
  for patch in (dict(flags=128),dict(flags=1),dict(flags=True),dict(flags=256),dict(flags=-1),dict(sender=36),dict(receiver=4),dict(commandSet=0),dict(commandId=102),dict(flags=None)):self.assertIsNone(external_device_notification(dict(message(),**patch)))
  self.assertEqual(external_device_notification(message(bytes((9,127))+bytes(127)))['records'][0]['length'],127)
 async def test_passive_status_does_not_complete_query(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.getWorkMode());await fixtures.until(lambda:any(f['commandId']==16 for f in self.client.frames()));r=next(f for f in self.client.frames() if f['commandId']==16);self.incoming();self.assertEqual(len(self.gimbal.experimental.pending),1);self.incoming(bytes([0,62,1,2]),128,16,r['sequence']);self.assertEqual((await task)['sourceMode'],'Fpv')
