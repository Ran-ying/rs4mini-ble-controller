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
    async def test_profile_copies_observer_and_no_writes(self):
        self.incoming();self.assertIsNone(self.gimbal.appCommands.handheldStickStatus);self.gimbal.appCommands.useProfile('ronin-2.2.2');errors=[];self.gimbal.onError=errors.append
        def observer(status):status['sourceStickX']=10;raise ValueError('observer')
        self.gimbal.onAppStatus=observer;self.incoming();r=self.gimbal.app_commands.handheld_stick_status;self.assertEqual(r['sourceStickX'],-32768);r['rawStateWord']=0;self.assertEqual(self.gimbal.appCommands.handheldStickStatus['rawStateWord'],32771);self.assertEqual(len(errors),1);self.assertEqual(self.client.frames(),[]);self.assertIsNone(self.gimbal.appCommands.userParameterStatus);self.assertIsNone(self.gimbal.appCommands.calibrationStatus)
    async def test_bad_frames_retain_cache_source_change_clears(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2');self.incoming();before=self.gimbal.appCommands.handheldStickStatus;self.incoming(bytes(5));self.incoming(flags=128);self.incoming(flags=1);self.assertEqual(self.gimbal.appCommands.handheldStickStatus,before);self.gimbal.appCommands.useProfile('ronin-2.2.2');self.assertIsNone(self.gimbal.appCommands.handheldStickStatus);self.incoming();self.gimbal.experimental.useProfile('rs3');self.assertIsNone(self.gimbal.appCommands.handheldStickStatus);self.incoming();self.assertIsNone(self.gimbal.appCommands.handheldStickStatus);self.assertEqual(self.client.frames(),[])
    async def test_disconnect_clears_no_control_or_subscribe(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2');self.incoming();await self.gimbal.disconnect();self.assertIsNone(self.gimbal.appCommands.handheldStickStatus);self.assertFalse(any(f['commandId'] in (18,88) for f in self.client.frames()))
    async def test_passive_report_keeps_pending_query(self):
        import asyncio
        self.gimbal.appCommands.useProfile('ronin-2.2.2');query=asyncio.create_task(self.gimbal.appCommands.getWorkMode());await fixtures.until(lambda:any(f['commandId']==16 for f in self.client.frames()));request=next(f for f in self.client.frames() if f['commandId']==16);self.incoming();self.assertEqual(len(self.gimbal.experimental.pending),1);self.assertEqual(self.gimbal.appCommands.handheldStickStatus['sourceStickX'],-32768);self.incoming(bytes([0,62,1,2]),128,16,request['sequence']);self.assertEqual((await query)['sourceMode'],'Fpv')
