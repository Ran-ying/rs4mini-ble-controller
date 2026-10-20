import asyncio, unittest
import test_controller as fixtures
from test_app_commands import reply, sent

class RetiredUnverifiedTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.ControllerTests.asyncSetUp
    asyncTearDown = fixtures.ControllerTests.asyncTearDown

    async def test_absent_entries_and_ignored_reports_never_complete_query(self):
        a = self.gimbal.appCommands
        a.useProfile('ronin-2.2.2')
        for name in ('tutorialStatus','externalDeviceStatus','peripheralStatus','batteryStatus','handheldStickStatus','userParameterStatus',
                     'tutorial_status','external_device_status','peripheral_status','battery_status','handheld_stick_status','user_parameter_status'):
            self.assertFalse(hasattr(a,name),name)
        raw,events=[],[]
        self.gimbal.onMessage=raw.append
        self.gimbal.onAppStatus=events.append
        reports=((43,bytes(5)),(105,bytes((2,7,1,0,128,255,127,0,0))),(102,bytes((1,34,2,10,0))),(51,b'\x32'),(87,bytes(6)),(36,bytes(78)))
        def inject(sequence):
            for command,body in reports:
                reply(self.client,dict(sequence=sequence,commandId=command),body,lambda b:b.__setitem__(8,0))
        inject(1)
        self.assertEqual(len(raw),6);self.assertEqual(events,[]);self.assertEqual(self.client.frames(),[])
        task=asyncio.create_task(a.getFollowSensitivity())
        await fixtures.until(lambda:sent(self.client,16))
        request=sent(self.client,16);inject(request['sequence'])
        self.assertFalse(task.done());self.assertEqual(events,[])
        reply(self.client,request,(0,150,1,1));self.assertEqual((await task)['rawValue'],1)
        self.gimbal.experimental.useProfile('rs3');before=len(self.client.frames())
        with self.assertRaises((TypeError,ValueError)):
            await self.gimbal.experimental.query(kind='position')
        self.assertEqual(len(self.client.frames()),before)

    async def test_retained_abnormal_observer_copy_and_cleanup(self):
        a=self.gimbal.appCommands;a.useProfile('ronin-2.2.2');errors=[];self.gimbal.onError=errors.append
        def observer(s):
            s['sourceValues']['getSleepMode']=99
            raise ValueError('observer')
        self.gimbal.onAppStatus=observer
        reply(self.client,dict(sequence=1,commandId=39),bytes.fromhex('04ff3e6701aabb'),lambda b:b.__setitem__(8,0))
        self.assertEqual(a.abnormalStatus['sourceValues']['getSleepMode'],1);self.assertEqual(len(errors),1)
        snapshot=a.abnormalStatus;snapshot['sourceValues']['getSleepMode']=0
        self.assertEqual(a.abnormalStatus['sourceValues']['getSleepMode'],1)
        await self.gimbal.disconnect();self.assertIsNone(a.abnormalStatus)
