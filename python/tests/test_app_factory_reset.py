import asyncio,unittest
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_protocol import factory_reset_spec
class FactoryResetTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 async def test_hg724_branch_body(self):
  self.assertEqual(factory_reset_spec('HG724')['payload'].hex(),'010001')
  for p in ['HG702',103,True,None]:
   with self.assertRaises(ValueError):factory_reset_spec(p)
 async def test_ack_ownership_and_unverified_scope(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.app_commands.send_factory_settings_reset_request(sourcePlatform='HG724'));await fixtures.until(lambda:sent(self.client,0x13));r=sent(self.client,0x13);self.assertEqual(r['payload'].hex(),'010001')
  with self.assertRaises(Exception) as e:await self.gimbal.setVelocity(pan=.1)
  self.assertEqual(e.exception.code,'RS4MINI_BUSY');reply(self.client,r,[0,99]);result=await task;self.assertEqual(result['requestedSourcePlatform'],'HG724');self.assertEqual(result['bodyHex'],'63')
  for k in ['deviceVerified','physicalCompletionVerified','targetResetScopeVerified','persistenceVerified']:self.assertFalse(result[k])
 async def test_bad_profile_branch_and_options_before_frames(self):
  with self.assertRaises(ValueError):await self.gimbal.appCommands.sendFactorySettingsResetRequest(sourcePlatform='HG724')
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for opts in [{},dict(sourcePlatform='HG702'),dict(sourcePlatform=103),dict(sourcePlatform=True),dict(sourcePlatform='HG724',payload=[1,0,1]),dict(sourcePlatform='HG724',timeoutMs=0)]:
   with self.assertRaises((ValueError,TypeError)):await self.gimbal.appCommands.sendFactorySettingsResetRequest(**opts)
  self.assertEqual(self.client.frames(),[])
 async def test_wrong_ack_nack_never_save_query_or_retry(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendFactorySettingsResetRequest(sourcePlatform='HG724'));await fixtures.until(lambda:sent(self.client,0x13));r=sent(self.client,0x13);reply(self.client,dict(r,commandId=0x11),[0]);await asyncio.sleep(0);self.assertFalse(task.done());reply(self.client,r,[7])
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_DEVICE_ERROR');self.assertFalse(self.gimbal.experimental.pending);self.assertEqual(len([f for f in self.client.frames() if f['commandId']==0x13]),1);self.assertTrue(all(f['commandId'] in (1,0x13) for f in self.client.frames()))
 async def test_cancel_during_preamble_never_resets(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');blocked=asyncio.Event();started=asyncio.Event();original=self.client.write_gatt_char;first=True
  async def write(*args,**kwargs):
   nonlocal first
   if first:first=False;started.set();await blocked.wait()
   await original(*args,**kwargs)
  self.client.write_gatt_char=write;task=asyncio.create_task(self.gimbal.appCommands.sendFactorySettingsResetRequest(sourcePlatform='HG724'));await started.wait();stopping=asyncio.create_task(self.gimbal.stop());await asyncio.sleep(0);blocked.set();await stopping
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_OPERATION_CANCELLED');self.assertIsNone(sent(self.client,0x13))
 async def test_postwrite_cancel_and_timeout_no_repeat(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendFactorySettingsResetRequest(sourcePlatform='HG724'));await fixtures.until(lambda:sent(self.client,0x13));await self.gimbal.stop()
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_OPERATION_CANCELLED')
  with self.assertRaises(Exception) as e:await self.gimbal.appCommands.sendFactorySettingsResetRequest(sourcePlatform='HG724',timeoutMs=10)
  self.assertEqual(e.exception.code,'RS4MINI_RESPONSE_TIMEOUT');frames=self.client.frames();self.assertEqual(len([f for f in frames if f['commandId']==0x13]),2);self.assertTrue(all(f['commandId'] in (1,0x13) for f in frames));self.assertFalse(self.gimbal.experimental.pending)
 async def test_disconnect_reconnect_does_not_repeat_reset(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendFactorySettingsResetRequest(sourcePlatform='HG724'));await fixtures.until(lambda:sent(self.client,0x13));await self.client.disconnect()
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_DISCONNECTED');await self.gimbal.connect();self.assertEqual(len([f for c in self.clients for f in c.frames() if f['commandId']==0x13]),1);self.assertFalse(self.gimbal.experimental.pending);self.assertIsNone(self.gimbal.activeOperation)
