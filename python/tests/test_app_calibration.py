import asyncio
import unittest
import test_controller as fixtures
from test_app_commands import reply, sent
from rs4mini_sdk.app_calibration import calibration_records


class AppCalibrationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.ControllerTests.asyncSetUp
    asyncTearDown = fixtures.ControllerTests.asyncTearDown

    def incoming(self, payload, flags=0, mutate=None):
        reply(self.client, dict(sequence=1,commandId=0x6e), payload,
              lambda data: (data.__setitem__(8,flags), mutate(data) if mutate else None))

    async def test_no_ack_auto_tune_requests_and_strict_inputs(self):
        with self.assertRaises(ValueError):
            await self.gimbal.appCommands.sendAutoTuneRequest(start=True)
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        for start in (True,False):
            result=await self.gimbal.app_commands.send_auto_tune_request(start=start)
            request=sent(self.client,0x6a)
            self.assertEqual(request['payload'], bytes((0,1,int(start))))
            self.assertEqual(request['flags'],0)
            self.assertFalse(result['acknowledged'])
            self.assertFalse(result['acknowledgementRequested'])
            self.assertFalse(result['physicalCompletionVerified'])
            self.assertFalse(self.gimbal.experimental.pending)
        count=len(self.client.frames())
        for start in (1,None,'true'):
            with self.assertRaises(ValueError):
                await self.gimbal.appCommands.sendAutoTuneRequest(start=start)
        self.assertEqual(len(self.client.frames()),count)

    async def test_notifications_copy_unknown_fields_and_reset_across_profiles(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        errors=[]
        self.gimbal.onError=lambda error: errors.append(error)
        def observer(value):
            value['records'].clear()
            raise ValueError('observer')
        self.gimbal.onAppStatus=observer
        self.incoming([1,0,0,3,2,100,99,7,1,44])
        current=self.gimbal.appCommands.calibrationStatus
        self.assertEqual(current['state'],'Complete')
        self.assertEqual(current['records'][1]['rawHex'],'026463')
        self.assertEqual(len(errors),1)
        current['records'].clear()
        self.assertEqual(len(self.gimbal.appCommands.calibration_status['records']),3)
        self.incoming([0,2,77,255])
        self.assertIsNone(self.gimbal.appCommands.calibrationStatus['state'])
        self.assertIsNone(self.gimbal.appCommands.calibrationStatus['percent'])
        self.assertEqual(self.gimbal.appCommands.calibrationStatus['rawPercent'],255)
        for body in ([0,128]+[1]*128,[],[0],[0,1,1],[0,2,1],[1,0],[2,2,2,0],[0,2,2,100,4]):
            self.incoming(body)
        self.assertEqual(self.gimbal.appCommands.calibrationStatus['rawState'],77)
        self.incoming([0,0,2,2,100],flags=0x80)
        self.incoming([0,2,2,100],mutate=lambda data:data.__setitem__(4,0x24))
        self.assertEqual(self.gimbal.appCommands.calibrationStatus['rawState'],77)
        self.gimbal.experimental.useProfile('rs3')
        self.assertIsNone(self.gimbal.appCommands.calibrationStatus)
        self.incoming([0,2,1,50])
        self.assertIsNone(self.gimbal.appCommands.calibrationStatus)
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        self.incoming([0,2,1,60])
        await self.client.disconnect()
        self.assertIsNone(self.gimbal.appCommands.calibrationStatus)

    async def test_no_ack_inflight_write_cancel_does_not_replay(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        started,release=asyncio.Event(),asyncio.Event()
        original=self.client.write_gatt_char
        async def blocked(characteristic,data,response):
            if len(data)>=11 and data[10]==0x6a:
                started.set()
                await release.wait()
            await original(characteristic,data,response)
        self.client.write_gatt_char=blocked
        task=asyncio.create_task(self.gimbal.appCommands.sendAutoTuneRequest(start=True))
        await started.wait()
        stopping=asyncio.create_task(self.gimbal.stop())
        await asyncio.sleep(0)
        release.set()
        await stopping
        with self.assertRaises(Exception) as cancelled:
            await task
        self.assertEqual(cancelled.exception.code,'RS4MINI_OPERATION_CANCELLED')
        self.assertEqual(len([f for f in self.client.frames() if f['commandId']==0x6a]),1)
        self.assertFalse(self.gimbal.experimental.pending)

    async def test_duplicate_status_records_use_last_complete_value(self):
        decoded=calibration_records(bytes([0,2,1,10,0,2,3,20]))
        self.assertEqual(decoded['state'],'Failure')
        self.assertEqual(decoded['percent'],20)
        self.assertEqual(len(decoded['records']),2)
        self.assertEqual(calibration_records(bytes([0,2,255,0]))['state'],'UnKnown')

    async def test_explicit_disconnect_clears_reports_received_during_stop(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        original=self.client.write_gatt_char
        async def write_and_notify(characteristic,data,response):
            await original(characteristic,data,response)
            self.incoming([0,2,1,50])
        self.client.write_gatt_char=write_and_notify
        await self.gimbal.disconnect()
        self.assertIsNone(self.gimbal.appCommands.calibrationStatus)
