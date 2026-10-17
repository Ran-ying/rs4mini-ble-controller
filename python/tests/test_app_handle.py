import asyncio,unittest
import test_controller as fixtures
from test_app_commands import reply,sent
class HandleTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 async def test_empty_query_raw_values_source_bits_and_correlation(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.app_commands.get_handle_settings());await fixtures.until(lambda:sent(self.client,0x36));r=sent(self.client,0x36);self.assertEqual(r['payload'],b'')
  reply(self.client,dict(r,commandId=0x35),[0]*9);await asyncio.sleep(0);self.assertFalse(task.done());reply(self.client,r,[0,7,1,0,255,3,2,3,254,99]);result=await task
  self.assertEqual(len(result['values']),8);self.assertEqual(result['values'][0]['rawValue'],7);self.assertEqual(result['values'][3]['rawValue'],255);self.assertFalse(result['values'][5]['sourceBit0']);self.assertTrue(result['values'][6]['sourceBit0']);self.assertEqual(result['bodyHex'],'070100ff030203fe63');self.assertFalse(result['modelLayoutVerified']);self.assertIsNone(self.gimbal.appCommands.userParameterStatus);self.assertEqual(len(self.client.frames()),1)
 async def test_profile_and_options_before_frames(self):
  with self.assertRaises(ValueError):await self.gimbal.appCommands.getHandleSettings()
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for options in (dict(index=0),dict(timeoutMs=0),dict(timeoutMs=True)):
   with self.assertRaises((ValueError,TypeError)):await self.gimbal.appCommands.getHandleSettings(**options)
  self.assertEqual(self.client.frames(),[])
 async def test_short_and_negative_ack(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for body,code in [([0,1,2,3,4,5,6,7],'RS4MINI_PROTOCOL_ERROR'),([7],'RS4MINI_DEVICE_ERROR')]:
   previous=sent(self.client,0x36);task=asyncio.create_task(self.gimbal.appCommands.getHandleSettings());await fixtures.until(lambda:sent(self.client,0x36)!=previous);reply(self.client,sent(self.client,0x36),body)
   with self.assertRaises(Exception) as e:await task
   self.assertEqual(e.exception.code,code)
  self.assertFalse(self.gimbal.experimental.pending)
 async def test_timeout_disconnect_no_retry_or_writes(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  with self.assertRaises(Exception) as e:await self.gimbal.appCommands.getHandleSettings(timeoutMs=10)
  self.assertEqual(e.exception.code,'RS4MINI_RESPONSE_TIMEOUT');previous=sent(self.client,0x36);task=asyncio.create_task(self.gimbal.appCommands.getHandleSettings());await fixtures.until(lambda:sent(self.client,0x36)!=previous);await self.gimbal.disconnect()
  with self.assertRaises(Exception) as e:await task
  self.assertEqual(e.exception.code,'RS4MINI_DISCONNECTED');self.assertFalse(self.gimbal.experimental.pending);self.assertEqual(len([f for f in self.client.frames() if f['commandId']==0x36]),2);cleanup=[f for f in self.client.frames() if f['commandId']!=0x36];self.assertEqual(len(cleanup),3);self.assertTrue(all(f['commandSet']==4 and f['commandId']==1 and f['payload'].hex()=='000400040004000002' for f in cleanup))
