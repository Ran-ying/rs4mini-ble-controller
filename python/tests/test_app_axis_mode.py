import asyncio,unittest
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_axis_mode import axis_mode_write,axis_mode_reply
class AxisModeTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 async def test_four_source_enum_write_bodies(self):
  for mode,value in [('ThreeAxis',0),('TwoAxis',8),('Roll360',16),('ThreeDRoll360',24)]:self.assertEqual(axis_mode_write(mode)['payload'],bytes((34,1,value)))
 async def test_read_mask_and_unknown_bits_not_motor_field(self):
  def msg(b):return dict(sender=4,receiver=2,commandSet=4,commandId=16,flags=128,payload=bytes(b),raw=b'')
  for raw in [0,8,16,24,255]:
   r=axis_mode_reply(msg([0,34,9,raw]));self.assertEqual(r['rawValue'],raw);self.assertEqual(r['sourceModeValue'],(raw>>3)&3);self.assertEqual(r['unknownBits'],raw&231);self.assertFalse(r['modelLayoutVerified'])
  self.assertEqual(axis_mode_reply(msg([0,34,9,255]))['sourceMode'],'ThreeDRoll360')
  for body in [[0,35,9,24],[0,34,9],[7]]:
   with self.assertRaises(Exception):axis_mode_reply(msg(body))
 async def test_getter_queries_only34_and_preserves_header(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.app_commands.get_axis_mode());await fixtures.until(lambda:sent(self.client,16));r=sent(self.client,16);self.assertEqual(r['payload'],b'\x22');reply(self.client,r,[0,34,9,255]);result=await task;self.assertEqual(result['sourceMode'],'ThreeDRoll360');self.assertEqual(result['unknownBits'],231);self.assertEqual(result['parameters'][0]['headerByte'],9);self.assertTrue(all(f['commandId']==16 for f in self.client.frames()))
 async def test_owned_setter_ack_is_not_full_mode_transaction(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.app_commands.send_axis_mode_request(sourceMode='ThreeDRoll360'));await fixtures.until(lambda:sent(self.client,15));r=sent(self.client,15);self.assertEqual(r['payload'].hex(),'220118')
  with self.assertRaises(Exception) as e:await self.gimbal.setVelocity(pan=.1)
  self.assertEqual(e.exception.code,'RS4MINI_BUSY');reply(self.client,r,[0]);result=await task;self.assertEqual(result['requestedSourceMode'],'ThreeDRoll360');self.assertEqual(result['requestedRawValue'],24)
  for k in ['deviceVerified','physicalCompletionVerified','activePresetVerified','otherBitsPreservationVerified','persistenceVerified']:self.assertFalse(result[k])
  self.assertTrue(all(f['commandId'] in (1,15) for f in self.client.frames()));self.assertIsNone(self.gimbal.appCommands.userParameterStatus)
 async def test_source_profile_named_modes_and_options_validation(self):
  with self.assertRaises(ValueError):await self.gimbal.appCommands.sendAxisModeRequest(sourceMode='ThreeAxis')
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for opts in [{},dict(sourceMode='PF'),dict(sourceMode='FPV'),dict(sourceMode=24),dict(sourceMode=True),dict(sourceMode='ThreeAxis',index=34),dict(sourceMode='ThreeAxis',value=64),dict(sourceMode='ThreeAxis',timeoutMs=0)]:
   with self.assertRaises((ValueError,TypeError)):await self.gimbal.appCommands.sendAxisModeRequest(**opts)
  self.assertEqual(self.client.frames(),[])
 async def test_wrong_ack_nack_does_not_write_again_or_save(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendAxisModeRequest(sourceMode='TwoAxis'));await fixtures.until(lambda:sent(self.client,15));r=sent(self.client,15);reply(self.client,dict(r,commandId=16),[0]);await asyncio.sleep(0);self.assertFalse(task.done());reply(self.client,r,[7])
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_DEVICE_ERROR');self.assertTrue(all(f['commandId'] in (1,15) for f in self.client.frames()));self.assertEqual(len([f for f in self.client.frames() if f['commandId']==15]),1)
 async def test_cancel_preamble_ack_and_timeout_no_replay(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');blocked=asyncio.Event();started=asyncio.Event();original=self.client.write_gatt_char;first=True
  async def write(*args,**kwargs):
   nonlocal first
   if first:first=False;started.set();await blocked.wait()
   await original(*args,**kwargs)
  self.client.write_gatt_char=write;task=asyncio.create_task(self.gimbal.appCommands.sendAxisModeRequest(sourceMode='ThreeAxis'));await started.wait();stopping=asyncio.create_task(self.gimbal.stop());await asyncio.sleep(0);blocked.set();await stopping
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_OPERATION_CANCELLED');self.assertIsNone(sent(self.client,15))
  task=asyncio.create_task(self.gimbal.appCommands.sendAxisModeRequest(sourceMode='ThreeAxis'));await fixtures.until(lambda:sent(self.client,15));await self.gimbal.stop()
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_OPERATION_CANCELLED')
  with self.assertRaises(Exception) as e:await self.gimbal.appCommands.sendAxisModeRequest(sourceMode='ThreeAxis',timeoutMs=10)
  self.assertEqual(e.exception.code,'RS4MINI_RESPONSE_TIMEOUT');writes=[f for f in self.client.frames() if f['commandId']==15];self.assertEqual(len(writes),2);self.assertTrue(all(f['payload'].hex()=='220100' for f in writes));self.assertFalse(self.gimbal.experimental.pending)
 async def test_disconnect_reconnect_never_repeats_axis_mode(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendAxisModeRequest(sourceMode='Roll360'));await fixtures.until(lambda:sent(self.client,15));await self.client.disconnect()
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_DISCONNECTED');await self.gimbal.connect();self.assertEqual(len([f for c in self.clients for f in c.frames() if f['commandId']==15]),1)
