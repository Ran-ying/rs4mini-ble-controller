import asyncio,unittest
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_smooth_track import smooth_track_selection,smooth_track_write,smooth_track_reply
class SmoothTrackTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 async def test_patch_order_and_omitted_axes(self):
  for axes,body in [(dict(roll=True,yaw=True,pitch=True),'110101120101130101'),(dict(roll=False,yaw=True),'110101130100'),(dict(pitch=False),'120100')]:self.assertEqual(smooth_track_write(axes)['payload'].hex(),body)
 async def test_unknown_values_are_not_bit0_or_errors(self):
  def msg(b):return dict(sender=4,receiver=2,commandSet=4,commandId=16,flags=128,payload=bytes(b),raw=b'')
  r=smooth_track_reply(msg([0,17,9,1,18,9,3,19,9,255]),smooth_track_selection());self.assertTrue(r['values'][0]['enabled'])
  for v in r['values'][1:]:self.assertIsNone(v['enabled']);self.assertFalse(v['sourceEnabled']);self.assertFalse(v['withinSourceRange'])
  self.assertEqual(r['values'][2]['rawValue'],255)
  for body in [[0,18,9,1],[0,17,9],[7]]:
   with self.assertRaises(Exception):smooth_track_reply(msg(body),smooth_track_selection('yaw'))
 async def test_getter_reads_all_or_single_without_changing_settings(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.app_commands.get_smooth_track_axes());await fixtures.until(lambda:sent(self.client,16));r=sent(self.client,16);self.assertEqual(r['payload'].hex(),'111213');reply(self.client,r,[0,17,9,1,18,9,0,19,9,255]);result=await task;self.assertEqual([v['enabled'] for v in result['values']],[True,False,None]);self.assertEqual(result['values'][2]['headerByte'],9)
  task=asyncio.create_task(self.gimbal.appCommands.getSmoothTrackAxes(axis='pitch'));await fixtures.until(lambda:len([f for f in self.client.frames() if f['commandId']==16])==2);r=sent(self.client,16);self.assertEqual(r['payload'],b'\x12');reply(self.client,r,[0,18,9,0]);self.assertEqual((await task)['values'][0]['axis'],'pitch');self.assertTrue(all(f['commandId']==16 for f in self.client.frames()))
 async def test_snapshotted_patch_owned_until_ack(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');axes=dict(roll=False,yaw=True);task=asyncio.create_task(self.gimbal.app_commands.send_smooth_track_axes_request(axes=axes));await fixtures.until(lambda:sent(self.client,15));axes['yaw']=False;axes['pitch']=True;r=sent(self.client,15);self.assertEqual(r['payload'].hex(),'110101130100')
  with self.assertRaises(Exception) as e:await self.gimbal.setVelocity(pan=.1)
  self.assertEqual(e.exception.code,'RS4MINI_BUSY');reply(self.client,r,[0]);result=await task;self.assertEqual(result['requestedAxes'],dict(yaw=True,roll=False))
  for k in ['deviceVerified','physicalCompletionVerified','activePresetVerified','atomicApplicationVerified','persistenceVerified']:self.assertFalse(result[k])
  self.assertIsNone(self.gimbal.appCommands.userParameterStatus);self.assertTrue(all(f['commandId'] in (1,15) for f in self.client.frames()))
 async def test_profile_empty_unknown_and_nonboolean_arguments(self):
  with self.assertRaises(ValueError):await self.gimbal.appCommands.sendSmoothTrackAxesRequest(axes=dict(yaw=True))
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for axes in [{},dict(yaw=1),dict(yaw=None),dict(enabled=True),dict(yaw=True,index=17),[True],None]:
   with self.assertRaises((ValueError,TypeError)):await self.gimbal.appCommands.sendSmoothTrackAxesRequest(axes=axes)
  with self.assertRaises(TypeError):await self.gimbal.appCommands.sendSmoothTrackAxesRequest(axes=dict(yaw=True),value=1)
  with self.assertRaises(ValueError):await self.gimbal.appCommands.getSmoothTrackAxes(axis='pan')
  self.assertEqual(self.client.frames(),[])
 async def test_wrong_ack_nack_no_retry_or_extra_fields(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendSmoothTrackAxesRequest(axes=dict(yaw=True,pitch=True,roll=True)));await fixtures.until(lambda:sent(self.client,15));r=sent(self.client,15);reply(self.client,dict(r,commandId=16),[0]);await asyncio.sleep(0);self.assertFalse(task.done());reply(self.client,r,[7])
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_DEVICE_ERROR');self.assertEqual(len([f for f in self.client.frames() if f['commandId']==15]),1);self.assertTrue(all(f['commandId'] in (1,15) for f in self.client.frames()))
 async def test_cancel_preamble_postwrite_and_timeout_no_repeat(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');blocked=asyncio.Event();started=asyncio.Event();original=self.client.write_gatt_char;first=True
  async def write(*args,**kwargs):
   nonlocal first
   if first:first=False;started.set();await blocked.wait()
   await original(*args,**kwargs)
  self.client.write_gatt_char=write;task=asyncio.create_task(self.gimbal.appCommands.sendSmoothTrackAxesRequest(axes=dict(pitch=False)));await started.wait();stopping=asyncio.create_task(self.gimbal.stop());await asyncio.sleep(0);blocked.set();await stopping
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_OPERATION_CANCELLED');self.assertIsNone(sent(self.client,15));task=asyncio.create_task(self.gimbal.appCommands.sendSmoothTrackAxesRequest(axes=dict(pitch=False)));await fixtures.until(lambda:sent(self.client,15));await self.gimbal.stop()
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_OPERATION_CANCELLED')
  with self.assertRaises(Exception) as e:await self.gimbal.appCommands.sendSmoothTrackAxesRequest(axes=dict(pitch=False),timeoutMs=10)
  self.assertEqual(e.exception.code,'RS4MINI_RESPONSE_TIMEOUT');writes=[f for f in self.client.frames() if f['commandId']==15];self.assertEqual(len(writes),2);self.assertTrue(all(f['payload'].hex()=='120100' for f in writes))
 async def test_disconnect_reconnect_no_batch_repeat(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendSmoothTrackAxesRequest(axes=dict(yaw=True,pitch=True,roll=True)));await fixtures.until(lambda:sent(self.client,15));await self.client.disconnect()
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_DISCONNECTED');await self.gimbal.connect();self.assertEqual(len([f for c in self.clients for f in c.frames() if f['commandId']==15]),1)
