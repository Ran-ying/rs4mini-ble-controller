import asyncio,json,pathlib,unittest
import test_controller as fixtures
from test_app_commands import reply
from rs4mini_sdk.app_sensor_calibration import sensor_calibration_notification
VECTORS=json.loads((pathlib.Path(__file__).resolve().parents[2]/'node/test/fixtures/sensor-calibration.json').read_text())
def body():return bytes.fromhex('6403aabb')
def message(payload=None,flags=0):return dict(sender=4,receiver=2,commandSet=4,commandId=48,flags=flags,payload=body() if payload is None else payload)
class SensorCalibrationTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 def incoming(self,payload=None,flags=0,command=48,sequence=1):reply(self.client,dict(sequence=sequence,commandId=command),body() if payload is None else payload,lambda data:data.__setitem__(8,flags))
 async def test_shared_vectors(self):
  for v in VECTORS:
   r=sensor_calibration_notification(message(bytes.fromhex(v['bodyHex'])))
   for k,value in v['expected'].items():self.assertEqual(r['deviceVerified' if k=='targetDeviceVerified' else k],value)
   self.assertFalse(r['requestAssociationVerified']);self.assertFalse(r['modelLayoutVerified'])
 async def test_all_unsigned_bytes_and_explicit_sensor_enum(self):
  states={0:'COMPLETE',1:'PROCESSING',3:'FAIL',9:'OTHER'}
  for raw in range(256):
   r=sensor_calibration_notification(message(bytes((raw,raw))));self.assertEqual(r['rawProgressValue'],raw);self.assertEqual(r['rawStatus'],raw);self.assertEqual(r['sourceStatus'],states.get(raw,'OTHER'));self.assertEqual(r['sourceStatusKnown'],raw in states);self.assertNotIn('inProgress',r)
 async def test_short_and_wrong_envelopes(self):
  for payload in (b'',b'\0',[]):self.assertIsNone(sensor_calibration_notification(message(payload)))
  for patch in (dict(flags=128),dict(flags=1),dict(flags=True),dict(flags=256),dict(flags=-1),dict(sender=36),dict(receiver=4),dict(commandSet=0),dict(commandId=8),dict(commandId=110),dict(flags=None)):self.assertIsNone(sensor_calibration_notification(dict(message(),**patch)))
 async def test_profile_copies_observer_no_writes_other_domains(self):
  self.incoming();self.assertIsNone(self.gimbal.appCommands.sensorCalibrationStatus);self.gimbal.appCommands.useProfile('ronin-2.2.2');errors=[];self.gimbal.onError=errors.append
  def observer(status):status['rawStatus']=0;raise ValueError('sensorObserver')
  self.gimbal.onAppStatus=observer;self.incoming();r=self.gimbal.app_commands.sensor_calibration_status;self.assertEqual(r['rawStatus'],3);r['sourceStatus']='COMPLETE';self.assertEqual(self.gimbal.appCommands.sensorCalibrationStatus['sourceStatus'],'FAIL');self.assertEqual(len(errors),1);self.assertEqual(self.client.frames(),[]);self.assertIsNone(self.gimbal.appCommands.calibrationStatus);self.assertFalse(hasattr(self.gimbal.appCommands,"externalDeviceStatus"));self.assertEqual(self.gimbal.experimental.status,{})
 async def test_invalid_retains_cache_source_and_disconnect_clear(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');self.incoming();before=self.gimbal.appCommands.sensorCalibrationStatus;self.incoming(b'\0');self.incoming(flags=128);self.incoming(flags=1);self.assertEqual(self.gimbal.appCommands.sensorCalibrationStatus,before);self.gimbal.appCommands.useProfile('ronin-2.2.2');self.assertIsNone(self.gimbal.appCommands.sensorCalibrationStatus);self.incoming();self.gimbal.experimental.useProfile('rs3');self.assertIsNone(self.gimbal.appCommands.sensorCalibrationStatus);self.incoming();self.assertIsNone(self.gimbal.appCommands.sensorCalibrationStatus);self.gimbal.appCommands.useProfile('ronin-2.2.2');self.incoming();await self.gimbal.disconnect();self.assertIsNone(self.gimbal.appCommands.sensorCalibrationStatus)
 async def test_complete_report_cannot_finish_pending_query(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.getWorkMode());await fixtures.until(lambda:any(f['commandId']==16 for f in self.client.frames()));r=next(f for f in self.client.frames() if f['commandId']==16);self.incoming(bytes((100,0)));self.assertEqual(len(self.gimbal.experimental.pending),1);self.incoming(bytes([0,62,1,2]),128,16,r['sequence']);self.assertEqual((await task)['sourceMode'],'Fpv');self.assertFalse(any(f['commandId']==8 for f in self.client.frames()))
