import asyncio,unittest
import test_controller as fixtures
from test_app_commands import reply
from rs4mini_sdk.app_protocol import app_reply
from rs4mini_sdk.app_calibration import calibration_notification
from rs4mini_sdk.telemetry import decode_gimbal_telemetry
from rs4mini_sdk.experimental_protocol import decode_research_status
from rs4mini_sdk.protocol import frame,crc16

def message(flags=128,payload=b'\0',command=15):return dict(sender=4,receiver=2,commandSet=4,commandId=command,flags=flags,payload=payload,raw=b'x')
class PlainEnvelopeTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 async def test_ack_rejects_cipher_flags_before_status(self):
  for flags in (129,130,131,132,133,134,135,-128,384,128.5,True,None):
   for status in (0,7):
    with self.assertRaises(Exception) as error:app_reply(message(flags,bytes((status,))),15)
    self.assertEqual(error.exception.code,'RS4MINI_PROTOCOL_ERROR')
  self.assertTrue(app_reply(message(),15)['acknowledged'])
  with self.assertRaises(Exception) as error:app_reply(message(128,b'\7'),15)
  self.assertEqual(error.exception.code,'RS4MINI_DEVICE_ERROR')
 async def test_typed_decoders_reject_encrypted_or_wrong_feedback_type(self):
  for flags in (1,2,3,4,5,6,7,128,None,-1,256,True):
   self.assertIsNone(decode_gimbal_telemetry(message(flags,bytes(49),5)));self.assertIsNone(calibration_notification(message(flags,bytes((0,2,2,100)),110)))
  for flags in (1,2,3,4,5,6,7,None,-1,256,True):self.assertIsNone(decode_research_status(message(flags,bytes((100,1)),48),'rs3'))
 async def test_encrypted_read_cannot_advance_parameter_write(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.setMotorSettings(forbidSelfie=True));await fixtures.until(lambda:any(f['commandId']==16 for f in self.client.frames()));r=next(f for f in self.client.frames() if f['commandId']==16);reply(self.client,r,bytes((0,35,1,0)),lambda b:b.__setitem__(8,131))
  with self.assertRaises(Exception) as error:await task
  self.assertEqual(error.exception.code,'RS4MINI_PROTOCOL_ERROR');self.assertFalse(any(f['commandId']==15 for f in self.client.frames()));self.assertEqual(self.gimbal.experimental.pending,{})
 async def test_cipher_auto_tune_status_does_not_replace_cache(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');reply(self.client,dict(sequence=1,commandId=110),bytes((0,2,1,20)),lambda b:b.__setitem__(8,0));before=self.gimbal.appCommands.calibrationStatus;reply(self.client,dict(sequence=1,commandId=110),bytes((0,2,2,100)),lambda b:b.__setitem__(8,3));self.assertEqual(self.gimbal.appCommands.calibrationStatus,before);self.assertEqual(self.client.frames(),[])
 async def test_cipher_feedback_remains_raw_without_joint_cache(self):
  raw=[];self.gimbal.onMessage=raw.append;payload=bytearray(49);payload[16:18]=(500).to_bytes(2,'little',signed=True);b=bytearray(frame(1,4,5,payload,flags=3));b[4]=4;b[5]=2;b[-2:]=crc16(b[:-2]).to_bytes(2,'little');self.client.notify(None,b);self.assertEqual(len(raw),1);self.assertEqual(raw[0]['flags'],3);self.assertIsNone(self.gimbal.latestTelemetry)
