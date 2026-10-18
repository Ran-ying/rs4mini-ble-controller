import asyncio,json,unittest
from pathlib import Path
import test_controller as fixtures
from test_app_commands import reply
from rs4mini_sdk.app_program_status import program_status_notification
VECTORS=json.loads((Path(__file__).resolve().parents[2]/'node/test/fixtures/program-status.json').read_text())
def body():return bytes.fromhex('00620401020304')
def msg(command=107,payload=None,flags=0):return dict(sender=4,receiver=2,commandSet=4,commandId=command,payload=body() if payload is None else payload,flags=flags)
class ProgramStatusTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 def incoming(self,command=107,payload=None,flags=0,sequence=1):reply(self.client,dict(sequence=sequence,commandId=command),body() if payload is None else payload,lambda data:data.__setitem__(8,flags))
 async def test_shared_vectors(self):
  for v in VECTORS:
   r=program_status_notification(msg(v['commandId'],bytes.fromhex(v['bodyHex'])));self.assertIsNotNone(r)
   for k,value in v['expected'].items():self.assertEqual(r[k],value,v['name']+': '+k)
   self.assertEqual(r['bodyHex'],v['bodyHex'])
   for k in ('deviceVerified','modelLayoutVerified','programCorrelationVerified','physicalCompletionVerified'):self.assertFalse(r[k])
 async def test_envelope_rejection(self):
  for patch in (dict(flags=128),dict(flags=1),dict(flags=True),dict(flags=256),dict(sender=36),dict(receiver=4),dict(commandSet=0),dict(commandId=98),dict(payload=[])):self.assertIsNone(program_status_notification(dict(msg(),**patch)))
  self.assertIsNotNone(program_status_notification(msg(flags=64)))
 async def test_malformed_no_partial_candidate(self):
  for h in ('','00','0062','006204010203','006203010203','006280','00fe00620401'):self.assertIsNone(program_status_notification(msg(payload=bytes.fromhex(h))))
  self.assertIsNone(program_status_notification(msg(56,bytes(3))));self.assertIsNone(program_status_notification(msg(100,bytes(4))))
 async def test_profile_copied_cache_observer_zero_sends(self):
  self.incoming();self.assertIsNone(self.gimbal.appCommands.programStatus);self.gimbal.appCommands.useProfile('ronin-2.2.2');errors=[];self.gimbal.onError=errors.append
  def observer(s):
   s['records'][0]['sourceValues']['status']=99
   raise ValueError('program observer')
  self.gimbal.onAppStatus=observer;self.incoming();r=self.gimbal.app_commands.program_status;r['records'][0]['sourceValues']['status']=77;self.assertEqual(self.gimbal.appCommands.programStatus['records'][0]['sourceValues']['status'],1);self.assertEqual(len(errors),1);self.assertEqual(self.client.frames(),[]);self.assertIsNone(self.gimbal.appCommands.batteryStatus)
 async def test_no_cross_frame_record_retention(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');self.incoming();self.incoming(100,bytes.fromhex('feffff0080'));self.assertEqual(self.gimbal.appCommands.programStatus['records'],[]);self.assertEqual(self.gimbal.appCommands.programStatus['sourceValues']['currentPictures'],65535);self.incoming(107,bytes.fromhex('00fe00'));self.assertIsNone(self.gimbal.appCommands.programStatus['records'][0]['sourceValues'])
 async def test_invalid_keeps_cache_profile_disconnect_clear(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');self.incoming();before=self.gimbal.appCommands.programStatus;self.incoming(payload=bytes.fromhex('006203010203'));self.incoming(flags=128);self.assertEqual(self.gimbal.appCommands.programStatus,before);self.gimbal.experimental.useProfile('rs3');self.assertIsNone(self.gimbal.appCommands.programStatus);self.incoming();self.assertIsNone(self.gimbal.appCommands.programStatus);self.gimbal.appCommands.useProfile('ronin-2.2.2');self.incoming();await self.gimbal.disconnect();self.assertIsNone(self.gimbal.appCommands.programStatus)
 async def test_notifications_do_not_resolve_query_or_write(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');q=asyncio.create_task(self.gimbal.appCommands.getWorkMode());await fixtures.until(lambda:any(f['commandId']==16 for f in self.client.frames()));r=next(f for f in self.client.frames() if f['commandId']==16);writes=len(self.client.frames());self.incoming(flags=64,sequence=r['sequence']);self.incoming(56,bytes.fromhex('0b010264'),64);self.incoming(100,bytes.fromhex('0101000200'),64);self.assertEqual(len(self.gimbal.experimental.pending),1);self.assertEqual(len(self.client.frames()),writes);self.incoming(16,bytes([0,62,1,2]),128,r['sequence']);self.assertEqual((await q)['sourceMode'],'Fpv')
