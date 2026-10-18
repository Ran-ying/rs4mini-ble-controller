import asyncio,json,pathlib,unittest
import test_controller as fixtures
from rs4mini_sdk.app_parameter_subscription import parameter_subscription_keys,parameter_subscription_spec,parameter_subscription_frame,parameter_subscription_sent
from rs4mini_sdk.telemetry import DumlStreamDecoder
VECTORS=json.loads((pathlib.Path(__file__).resolve().parents[2]/'node/test/fixtures/parameter-subscription.json').read_text())
class ParameterSubscriptionTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 async def test_vectors(self):
  for v in VECTORS:
   s=parameter_subscription_spec(v['keys']);self.assertEqual(s['requestBodyHex'],v['bodyHex']);frames=DumlStreamDecoder().push(parameter_subscription_frame(123,s));self.assertEqual(len(frames),1);self.assertEqual(frames[0]['receiver'],229);self.assertEqual(frames[0]['flags'],0);self.assertEqual(frames[0]['payload'].hex(),v['bodyHex'])
 async def test_catalog_and_conditions(self):
  keys=parameter_subscription_keys();self.assertEqual(len(keys),152);keys.pop();self.assertEqual(len(parameter_subscription_keys()),152)
  s=parameter_subscription_spec(parameter_subscription_keys());self.assertEqual(len(s['payload']),36);self.assertEqual(len(s['metadataConditionalKeys']),21);self.assertEqual(len(s['modelConditionalKeys']),2);self.assertEqual(sum(len(g['channels']) for g in s['sourceGroups']),121)
  result=parameter_subscription_sent(s);self.assertNotIn('payload',result)
  for k,v in result.items():
   if k.endswith('Verified') or k in ('acknowledged','acknowledgementRequested'):self.assertIs(v,False)
 async def test_invalid_and_profile_before_writes(self):
  with self.assertRaises(ValueError):await self.gimbal.appCommands.sendParameterSubscriptionRequest(keys=['UserProfile'])
  self.gimbal.appCommands.useProfile('ronin-2.2.2')
  for keys in ([],None,'UserProfile',[0],['__proto__'],['unknown'],['UserProfile']*153):
   with self.assertRaises(ValueError):await self.gimbal.appCommands.sendParameterSubscriptionRequest(keys=keys)
  self.assertEqual(self.client.frames(),[])
 async def test_send_once_no_ack_or_automatic_refresh(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');result=await self.gimbal.appCommands.send_parameter_subscription_request(keys=['UserProfile'])
  self.assertEqual(result['requestedKeys'],['UserProfile']);frames=self.client.frames();self.assertEqual([f['commandId'] for f in frames],[1,1,1,18]);self.assertEqual(frames[-1]['payload'].hex(),'100001');self.assertEqual(self.gimbal.experimental.pending,{})

 async def test_stop_during_preamble_cancels_request(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');task=asyncio.create_task(self.gimbal.appCommands.sendParameterSubscriptionRequest(keys=['UserProfile']));await fixtures.until(lambda:bool(self.client.writes));await self.gimbal.stop()
  with self.assertRaises(Exception) as raised:await task
  self.assertEqual(raised.exception.code,'RS4MINI_OPERATION_CANCELLED');self.assertTrue(all(f['commandId']==1 for f in self.client.frames()))
 async def test_started_multichunk_frame_finishes_before_stop_cleanup(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');started=asyncio.Event();release=asyncio.Event();original=self.client.write_gatt_char
  async def write(characteristic,data,response):
   if data[0]==85 and data[9]==4 and data[10]==18:started.set();await release.wait()
   await original(characteristic,data,response)
  self.client.write_gatt_char=write;task=asyncio.create_task(self.gimbal.appCommands.sendParameterSubscriptionRequest(keys=self.gimbal.appCommands.parameterSubscriptionKeys));await started.wait()
  with self.assertRaises(Exception) as raised:await self.gimbal.setVelocity(pan=.1)
  self.assertEqual(raised.exception.code,'RS4MINI_BUSY');stop=asyncio.create_task(self.gimbal.stop());await asyncio.sleep(0);release.set();await stop
  with self.assertRaises(Exception) as raised:await task
  self.assertEqual(raised.exception.code,'RS4MINI_OPERATION_CANCELLED');frames=self.client.frames();self.assertEqual([f['commandId'] for f in frames],[1,1,1,18,1,1,1]);self.assertEqual(len(frames[3]['payload']),36);self.assertEqual(self.gimbal.experimental.pending,{})
 async def test_write_timeout_disconnects_without_replay(self):
  self.gimbal.appCommands.useProfile('ronin-2.2.2');original=self.client.write_gatt_char;attempts=[]
  async def write(characteristic,data,response):
   if data[0]==85 and data[10]==18:attempts.append(1);await asyncio.Event().wait()
   await original(characteristic,data,response)
  self.client.write_gatt_char=write
  with self.assertRaises(Exception) as raised:await self.gimbal.appCommands.sendParameterSubscriptionRequest(keys=['UserProfile'])
  self.assertEqual(raised.exception.code,'RS4MINI_IO_TIMEOUT');self.assertEqual(attempts,[1]);self.assertFalse(self.client.is_connected)
