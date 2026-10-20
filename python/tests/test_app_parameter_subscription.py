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
