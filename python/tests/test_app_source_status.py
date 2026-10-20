import asyncio,unittest
import test_controller as fixtures
from test_app_commands import reply
from rs4mini_sdk.app_source_status import source_status_notification

def body():return bytes.fromhex('04ff3e6701aabb')
def msg(command=39,payload=None,flags=0):return dict(sender=4,receiver=2,commandSet=4,commandId=command,payload=body() if payload is None else payload,flags=flags)
class SourceStatusTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 def incoming(self,command=39,payload=None,flags=0,sequence=1):reply(self.client,dict(sequence=sequence,commandId=command),body() if payload is None else payload,lambda data:data.__setitem__(8,flags))
 async def test_abnormal_fields_and_composite_excludes_yaw(self):
  r=source_status_notification(msg());v=r['sourceValues'];self.assertEqual(len(v),22);self.assertEqual(v['getGimbalGravity'],3);self.assertEqual(v['getSleepMode'],1);self.assertEqual(v['getFanDirection'],1);self.assertTrue(v['isPanoReady']);self.assertTrue(v['isMotorProtected']);self.assertTrue(v['isYawLocked']);self.assertFalse(v['isGimbalLocked']);self.assertEqual(r['bodyHex'],body().hex());self.assertFalse(r['modelLayoutVerified'])
  for value in (1,2,4,248):self.assertEqual(source_status_notification(msg(payload=bytes([value])+body()[1:]))['sourceValues']['isGimbalLocked'],value in (1,2))
 async def test_battery_preserves_raw255_tail_and_distinct_envelope(self):
  for value in (0,100,255):
   r=source_status_notification(msg(51,bytes([value,99])));self.assertEqual(r['rawCapacityValue'],value);self.assertEqual(r['bodyHex'],bytes([value,99]).hex());self.assertEqual(r['sourceGetter'],'getCapacityPercentage')
  self.assertIsNone(source_status_notification(dict(msg(51,b'\x32'),commandSet=13,commandId=2)))
 async def test_full_request_envelope_required(self):
  for command in (39,51):
   for patch in (dict(payload=bytes(4 if command==39 else 0)),dict(flags=128),dict(flags=1),dict(flags=True),dict(flags=256),dict(flags=-1),dict(sender=36),dict(receiver=4),dict(commandSet=0),dict(commandId=40),dict(payload=[])):
    self.assertIsNone(source_status_notification(dict(msg(command),**patch)))
 async def test_statuses_do_not_complete_pending_query(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');q=asyncio.create_task(self.gimbal.appCommands.getWorkMode());await fixtures.until(lambda:any(f['commandId']==16 for f in self.client.frames()));r=next(f for f in self.client.frames() if f['commandId']==16);self.incoming();self.incoming(51,b'\xff');self.assertEqual(len(self.gimbal.experimental.pending),1);self.incoming(16,bytes([0,62,1,2]),128,r['sequence']);self.assertEqual((await q)['sourceMode'],'Fpv')
