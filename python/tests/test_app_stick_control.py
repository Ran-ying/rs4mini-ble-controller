import asyncio,json,unittest
from pathlib import Path
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_handheld_stick import handheld_stick_control_payload,handheld_stick_control_reply

def message(payload,flags=128):return dict(sender=4,receiver=2,commandSet=4,commandId=88,flags=flags,payload=bytes(payload),raw=b'')
class StickControlTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=fixtures.ControllerTests.asyncSetUp
 asyncTearDown=fixtures.ControllerTests.asyncTearDown
 async def test_shared_contracts_and_boolean_domain(self):
  rows=json.loads((Path(__file__).resolve().parents[2]/'node/test/fixtures/handheld-stick-control.json').read_text());self.assertEqual(len(rows),3)
  for v in rows:
   r=handheld_stick_control_reply(message(bytes.fromhex(v['payloadHex'])),v['enabled']);self.assertEqual(handheld_stick_control_payload(v['enabled']),bytes((int(v['enabled']),)))
   for k,value in v['expected'].items():self.assertEqual(r[k],value)
   for key in ('deviceVerified','physicalCompletionVerified','readbackVerified','persistenceVerified','notificationAssociationVerified'):self.assertFalse(r[key])
  for value in (None,0,1,'true',{},[]):
   with self.assertRaises(ValueError):handheld_stick_control_payload(value)
  for flags in range(129,136):
   with self.assertRaises(Exception) as error:handheld_stick_control_reply(message((0,),flags),True)
   self.assertEqual(error.exception.code,'RS4MINI_PROTOCOL_ERROR')
