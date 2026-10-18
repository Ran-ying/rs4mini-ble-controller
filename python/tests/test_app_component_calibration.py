import asyncio,json,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_component_calibration import component_calibration_reply,component_calibration_payload

def message(payload,command=8):return dict(sender=4,receiver=2,commandSet=4,commandId=command,flags=128,payload=bytes(payload),raw=b'')
class ComponentCalibrationTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 async def test_shared_vectors_and_uint8_domains(self):
  vectors=json.loads((Path(__file__).resolve().parents[2]/'node/test/fixtures/component-calibration.json').read_text());self.assertEqual(len(vectors),7)
  for v in vectors:
   r=component_calibration_reply(message(bytes.fromhex(v['payloadHex'])),128)
   for key,value in v['expected'].items():self.assertEqual(r[key],value,v['name'])
   self.assertFalse(r['physicalCompletionVerified']);self.assertFalse(r['businessRequestAssociationVerified'])
  for v in range(256):
   r=component_calibration_reply(message((0,v,v)),0)['calibration'];self.assertEqual((r['rawPart'],r['rawStatus']),(v,v));self.assertEqual(r['sourcePartKnown'],v<10);self.assertEqual(r['sourceStatusKnown'],v<3)
 async def test_invalid_spec_has_no_sends(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for options in ({},{'sourcePart':'GYRO'},{'sourcePart':0},{'sourcePart':'AUTO','motorEnabled':True},{'sourcePart':'AUTO','timeoutMs':True}):
   with self.assertRaises((ValueError,TypeError)):await self.gimbal.appCommands.sendComponentCalibrationRequest(**options)
  self.assertEqual(self.client.frames(),[]);self.assertEqual(component_calibration_payload('AUTO'),b'\0')
 async def test_fresh_motor_preflight_and_business_failure(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.send_component_calibration_request(sourcePart='AUTO'));await fixtures.until(lambda:sent(self.client,16));read=sent(self.client,16);self.assertEqual(read['payload'],b'\x23')
  with self.assertRaises(Exception) as error:await self.gimbal.setVelocity(pan=.1)
  self.assertEqual(error.exception.code,'RS4MINI_BUSY');reply(self.client,read,(0,35,1,128));await fixtures.until(lambda:sent(self.client,8));start=sent(self.client,8);self.assertEqual(start['payload'],b'\0');self.assertEqual(start['flags'],64);self.assertNotEqual(start['sequence'],read['sequence']);reply(self.client,start,(0,0,0));r=await task;self.assertTrue(r['acknowledged']);self.assertEqual(r['calibration']['sourceStatus'],'FAIL');self.assertEqual(r['motorPreflightRawValue'],128);self.assertIsNone(self.gimbal.appCommands.calibrationStatus);self.assertIsNone(self.gimbal.appCommands.sensorCalibrationStatus);self.assertIsNone(self.gimbal.latestTelemetry);self.assertFalse(any(f['commandId']==15 for f in self.client.frames()))
 async def test_preflight_failures_never_send_start(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for payload,flags,code in [((0,35,1,1),128,'RS4MINI_MOTOR_DISABLED'),((7,),128,'RS4MINI_DEVICE_ERROR'),((0,35,1),128,'RS4MINI_PROTOCOL_ERROR'),((0,35,1,0),131,'RS4MINI_PROTOCOL_ERROR')]:
   count=len([f for f in self.client.frames() if f['commandId']==16]);task=asyncio.create_task(self.gimbal.appCommands.sendComponentCalibrationRequest(sourcePart='AUTO'));await fixtures.until(lambda:len([f for f in self.client.frames() if f['commandId']==16])>count);reply(self.client,sent(self.client,16),payload,lambda b:b.__setitem__(8,flags))
   with self.assertRaises(Exception) as error:await task
   self.assertEqual(error.exception.code,code);self.assertIsNone(sent(self.client,8));self.assertEqual(self.gimbal.experimental.pending,{})
 async def test_cancel_read_then_ignore_late_response(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendComponentCalibrationRequest(sourcePart='AUTO'));await fixtures.until(lambda:sent(self.client,16));read=sent(self.client,16);await self.gimbal.stop()
  with self.assertRaises(Exception) as error:await task
  self.assertEqual(error.exception.code,'RS4MINI_OPERATION_CANCELLED');reply(self.client,read,(0,35,1,0));await asyncio.sleep(0);self.assertIsNone(sent(self.client,8));self.assertEqual(self.gimbal.experimental.pending,{})
 async def test_cancel_after_send_does_not_send_abort_or_replay(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendComponentCalibrationRequest(sourcePart='AUTO'));await fixtures.until(lambda:sent(self.client,16));reply(self.client,sent(self.client,16),(0,35,1,0));await fixtures.until(lambda:sent(self.client,8));start=sent(self.client,8);await self.gimbal.stop()
  with self.assertRaises(Exception) as error:await task
  self.assertEqual(error.exception.code,'RS4MINI_OPERATION_CANCELLED');reply(self.client,start,(0,0,1));self.assertEqual(len([f for f in self.client.frames() if f['commandId']==8]),1)
 async def test_ack_errors_and_short_body_release_without_caching(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for payload,flags,code in [((1,0,1),128,'RS4MINI_DEVICE_ERROR'),((),128,'RS4MINI_PROTOCOL_ERROR'),((0,0,1),131,'RS4MINI_PROTOCOL_ERROR'),((0,),128,None),((0,5),128,None)]:
   count=len([f for f in self.client.frames() if f['commandId']==16]);starts=len([f for f in self.client.frames() if f['commandId']==8]);task=asyncio.create_task(self.gimbal.appCommands.sendComponentCalibrationRequest(sourcePart='AUTO'));await fixtures.until(lambda:len([f for f in self.client.frames() if f['commandId']==16])>count);reply(self.client,sent(self.client,16),(0,35,1,0));await fixtures.until(lambda:len([f for f in self.client.frames() if f['commandId']==8])>starts);reply(self.client,sent(self.client,8),payload,lambda b:b.__setitem__(8,flags))
   if code:
    with self.assertRaises(Exception) as error:await task
    self.assertEqual(error.exception.code,code)
   else:
    r=await task;self.assertFalse(r['businessComplete']);self.assertIsNone(r['calibration'])
   self.assertEqual(self.gimbal.experimental.pending,{});self.assertIsNone(self.gimbal.appCommands.calibrationStatus)
 async def test_remaining_deadline_is_shared(self):
  from rs4mini_sdk.app_commands import AppCommands
  clock=[1];timeouts=[];advance=[.075]
  class Owner:
   _epoch=1
   async def _halt(self):pass
   def _check(self,operation):pass
   async def _run(self,name,body,flag):return await body(object())
  class Query:
   async def _query_payload_command(self,name,cmd,payload,timeout,**kw):
    timeouts.append(timeout)
    if cmd[1]==16:clock[0]+=advance[0];return message((0,35,1,0),16)
    return message((0,0,1))
  owner=Owner();owner.experimental=Query();app=AppCommands(owner);app._profile='ronin-2.2.2'
  with patch('rs4mini_sdk.app_commands.time',SimpleNamespace(monotonic=lambda:clock[0])):
   await app.sendComponentCalibrationRequest(sourcePart='AUTO',timeoutMs=100);self.assertAlmostEqual(timeouts[0],100);self.assertAlmostEqual(timeouts[1],25);advance[0]=.101;timeouts.clear()
   with self.assertRaises(Exception) as error:await app.sendComponentCalibrationRequest(sourcePart='AUTO',timeoutMs=100)
   self.assertEqual(error.exception.code,'RS4MINI_RESPONSE_TIMEOUT');self.assertEqual(len(timeouts),1)
if __name__=='__main__':unittest.main()
