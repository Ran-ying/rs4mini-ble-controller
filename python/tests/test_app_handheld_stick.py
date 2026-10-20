import unittest
import test_controller as fixtures
from test_app_commands import reply
from rs4mini_sdk.app_handheld_stick import handheld_stick_notification

def body():return bytes.fromhex('0080ff7f0380aabb')
def message(payload=None,flags=0):return dict(sender=4,receiver=2,commandSet=4,commandId=87,flags=flags,payload=body() if payload is None else payload)
class HandheldStickTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.ControllerTests.asyncSetUp
    asyncTearDown=fixtures.ControllerTests.asyncTearDown
    def incoming(self,payload=None,flags=0,command=87,sequence=1):reply(self.client,dict(sequence=sequence,commandId=command),body() if payload is None else payload,lambda data:data.__setitem__(8,flags))
    async def test_signed_endpoints_unknown_flags_and_tail(self):
        r=handheld_stick_notification(message());self.assertEqual((r['sourceStickX'],r['sourceStickY']),(-32768,32767));self.assertEqual(r['rawStateWord'],32771);self.assertEqual(r['unknownStateBits'],32768);self.assertTrue(r['sourceTriggerPressed']);self.assertTrue(r['sourceStickControlEnabled']);self.assertEqual(r['bodyHex'],body().hex());self.assertFalse(r['axisMappingVerified']);self.assertFalse(r['deviceVerified'])
    async def test_independent_bits_and_envelope_rejection(self):
        for word,trigger,enabled in ((0,False,False),(1,True,False),(2,False,True),(3,True,True),(65535,True,True)):
            b=body()[:4]+word.to_bytes(2,'little');r=handheld_stick_notification(message(b));self.assertEqual(r['sourceTriggerPressed'],trigger);self.assertEqual(r['sourceStickControlEnabled'],enabled)
        for patch in (dict(flags=128),dict(flags=1),dict(flags=True),dict(flags=256),dict(flags=-1),dict(sender=36),dict(receiver=4),dict(commandSet=0),dict(commandId=88),dict(payload=bytes(5)),dict(payload=[]),dict(flags=None)):
            self.assertIsNone(handheld_stick_notification(dict(message(),**patch)))
