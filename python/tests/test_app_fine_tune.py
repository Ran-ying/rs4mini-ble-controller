import asyncio,unittest
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_fine_tune import fine_tune_spec
class FineTuneTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 async def test_float32_truncation_axis_vectors(self):
  for axis,delta,hex_value,steps in [('pitch',-1.29,'f402',-12),('roll',1.29,'0c00',12),('roll',1.999999999,'1400',20),('pitch',-.09,'0002',0),('roll',-2,'ec00',-20)]:
   spec=fine_tune_spec(axis,delta);self.assertEqual(spec['payload'].hex(),hex_value);self.assertEqual(spec['encodedTenths'],steps)
 async def test_ack_owned_request_and_result_scope(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.app_commands.send_fine_tune_request(axis='pitch',adjustmentDegrees=-1.29));await fixtures.until(lambda:sent(self.client,7));r=sent(self.client,7);self.assertEqual(r['payload'].hex(),'f402')
  with self.assertRaises(Exception) as e:await self.gimbal.setVelocity(pan=.1)
  self.assertEqual(e.exception.code,'RS4MINI_BUSY');reply(self.client,r,[0]);result=await task;self.assertEqual(result['encodedTenths'],-12);self.assertEqual(result['nominalAdjustmentDegrees'],-1.2);self.assertEqual(result['requestedAdjustmentDegrees'],-1.29);self.assertFalse(result['physicalCompletionVerified']);self.assertFalse(result['stabilizationStateVerified'])
 async def test_profile_and_arguments_before_frames(self):
  with self.assertRaises(ValueError):await self.gimbal.appCommands.sendFineTuneRequest(axis='roll',adjustmentDegrees=1)
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for patch in [dict(axis='yaw'),dict(axis=0),dict(adjustmentDegrees=True),dict(adjustmentDegrees=2.1),dict(adjustmentDegrees=float('nan')),dict(adjustmentDegrees=float('inf')),dict(adjustmentDegrees=10**1000),dict(index=0),dict(timeoutMs=0)]:
   with self.assertRaises((ValueError,TypeError)):await self.gimbal.appCommands.sendFineTuneRequest(**dict(dict(axis='roll',adjustmentDegrees=1),**patch))
  self.assertEqual(self.client.frames(),[])
 async def test_wrong_command_and_negative_ack(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendFineTuneRequest(axis='roll',adjustmentDegrees=.1));await fixtures.until(lambda:sent(self.client,7));r=sent(self.client,7);reply(self.client,dict(r,commandId=15),[0]);await asyncio.sleep(0);self.assertFalse(task.done());reply(self.client,r,[7])
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_DEVICE_ERROR');self.assertFalse(self.gimbal.experimental.pending)
 async def test_cancel_preamble_never_sends_fine_frame(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');blocked=asyncio.Event();started=asyncio.Event();original=self.client.write_gatt_char;first=True
  async def write(*args,**kwargs):
   nonlocal first
   if first:first=False;started.set();await blocked.wait()
   await original(*args,**kwargs)
  self.client.write_gatt_char=write;task=asyncio.create_task(self.gimbal.appCommands.sendFineTuneRequest(axis='pitch',adjustmentDegrees=.1));await started.wait();stopping=asyncio.create_task(self.gimbal.stop());await asyncio.sleep(0);blocked.set();await stopping
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_OPERATION_CANCELLED');self.assertIsNone(sent(self.client,7))
 async def test_cancel_ack_timeout_no_replay_or_rollback(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendFineTuneRequest(axis='roll',adjustmentDegrees=.1));await fixtures.until(lambda:sent(self.client,7));await self.gimbal.stop()
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_OPERATION_CANCELLED')
  with self.assertRaises(Exception) as e:await self.gimbal.appCommands.sendFineTuneRequest(axis='roll',adjustmentDegrees=.1,timeoutMs=10)
  self.assertEqual(e.exception.code,'RS4MINI_RESPONSE_TIMEOUT');frames=self.client.frames();fine=[f for f in frames if f['commandId']==7];self.assertEqual(len(fine),2);self.assertTrue(all(f['payload'].hex()=='0100' for f in fine));self.assertTrue(all(f['commandId'] in (1,7) for f in frames));self.assertFalse(self.gimbal.experimental.pending)
