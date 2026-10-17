import asyncio,unittest
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_handle import handle_write_spec
class HandleWriteTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 async def test_single_named_fields_and_independent_defaults(self):
  for setting,value,hex_value in [('dualChannelMode',0,'00ffffffffffffff'),('tiltDirection',1,'ff01ffffffffffff'),('panDirection',1,'ffff01ffffffffff')]:self.assertEqual(handle_write_spec(setting,value)['payload'].hex(),hex_value)
  self.assertEqual(handle_write_spec('dualChannelMode',1)['payload'].hex(),'01ffffffffffffff')
 async def test_ack_ownership_and_unverified_result_scope(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.app_commands.send_handle_setting_request(setting='panDirection',value=1));await fixtures.until(lambda:sent(self.client,0x35));r=sent(self.client,0x35);self.assertEqual(r['payload'].hex(),'ffff01ffffffffff')
  with self.assertRaises(Exception) as e:await self.gimbal.setVelocity(pan=.1)
  self.assertEqual(e.exception.code,'RS4MINI_BUSY');reply(self.client,r,[0,99]);result=await task;self.assertEqual(result['setting'],'panDirection');self.assertEqual(result['requestedValue'],1);self.assertEqual(result['bodyHex'],'63')
  for key in ['deviceVerified','physicalCompletionVerified','unspecifiedByteSemanticsVerified','readbackVerified','persistenceVerified']:self.assertFalse(result[key])
  self.assertIsNone(self.gimbal.appCommands.userParameterStatus)
 async def test_bad_profile_fields_and_values_before_write(self):
  with self.assertRaises(ValueError):await self.gimbal.appCommands.sendHandleSettingRequest(setting='panDirection',value=1)
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for patch in [dict(setting='profile'),dict(setting='zoom2Speed'),dict(setting='rollDirection'),dict(setting=0),dict(value=True),dict(value=255),dict(value=-1),dict(value=.5),dict(value=float('nan')),dict(value=float('inf')),dict(value=10**1000),dict(index=2),dict(timeoutMs=0)]:
   with self.assertRaises((ValueError,TypeError)):await self.gimbal.appCommands.sendHandleSettingRequest(**dict(dict(setting='panDirection',value=1),**patch))
  self.assertEqual(self.client.frames(),[])
 async def test_wrong_ack_and_nack_do_not_query_cache_or_retry(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendHandleSettingRequest(setting='tiltDirection',value=0));await fixtures.until(lambda:sent(self.client,0x35));r=sent(self.client,0x35);reply(self.client,dict(r,commandId=0x36),[0]);await asyncio.sleep(0);self.assertFalse(task.done());reply(self.client,r,[7])
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_DEVICE_ERROR');self.assertFalse(self.gimbal.experimental.pending);self.assertEqual(len([f for f in self.client.frames() if f['commandId']==0x35]),1);self.assertTrue(all(f['commandId'] in (1,0x35) for f in self.client.frames()))
 async def test_cancel_during_preamble_never_sends_setting(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');blocked=asyncio.Event();started=asyncio.Event();original=self.client.write_gatt_char;first=True
  async def write(*args,**kwargs):
   nonlocal first
   if first:first=False;started.set();await blocked.wait()
   await original(*args,**kwargs)
  self.client.write_gatt_char=write;task=asyncio.create_task(self.gimbal.appCommands.sendHandleSettingRequest(setting='panDirection',value=1));await started.wait();stopping=asyncio.create_task(self.gimbal.stop());await asyncio.sleep(0);blocked.set();await stopping
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_OPERATION_CANCELLED');self.assertIsNone(sent(self.client,0x35))
 async def test_postwrite_cancel_and_timeout_no_repeat_or_rollback(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendHandleSettingRequest(setting='dualChannelMode',value=1));await fixtures.until(lambda:sent(self.client,0x35));await self.gimbal.stop()
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_OPERATION_CANCELLED')
  with self.assertRaises(Exception) as e:await self.gimbal.appCommands.sendHandleSettingRequest(setting='dualChannelMode',value=1,timeoutMs=10)
  self.assertEqual(e.exception.code,'RS4MINI_RESPONSE_TIMEOUT');frames=self.client.frames();writes=[f for f in frames if f['commandId']==0x35];self.assertEqual(len(writes),2);self.assertTrue(all(f['payload'].hex()=='01ffffffffffffff' for f in writes));self.assertTrue(all(f['commandId'] in (1,0x35) for f in frames));self.assertFalse(self.gimbal.experimental.pending)
