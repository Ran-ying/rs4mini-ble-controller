import asyncio
import unittest
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_system_calibration import system_calibration_fields

class AppSystemCalibrationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.ControllerTests.asyncSetUp
    asyncTearDown=fixtures.ControllerTests.asyncTearDown

    async def test_source_states_beyond_write_range(self):
        self.assertEqual([system_calibration_fields(v)['state'] for v in range(4)],['DEFAULT','START','FAIL','SUCCESS'])
        self.assertEqual(system_calibration_fields(3),dict(rawValue=3,state='SUCCESS'))

    async def test_unknown_states_retained(self):
        for value in range(4,256):self.assertEqual(system_calibration_fields(value),dict(rawValue=value,state=None))
        for value in (-1,True,256):
            with self.assertRaises(ValueError):system_calibration_fields(value)

    async def test_named_query_distinct_from_auto_tune_status(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.app_commands.get_auto_calibration_status())
        await fixtures.until(lambda:sent(self.client,0x10));r=sent(self.client,0x10)
        self.assertEqual(r['payload'],b'\x24')
        reply(self.client,dict(r,commandId=0x6e),[0,0,2,2,100]);await asyncio.sleep(0)
        self.assertFalse(task.done())
        reply(self.client,r,[0,36,9,3]);result=await task
        self.assertEqual(result['systemCalibration']['state'],'SUCCESS')
        self.assertEqual(result['parameters'][0]['headerByte'],9)
        self.assertFalse(result['physicalCompletionVerified'])

    async def test_fixed_start_owns_until_ack(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.app_commands.send_auto_calibration_request())
        await fixtures.until(lambda:sent(self.client,0x0f));r=sent(self.client,0x0f)
        self.assertEqual(r['payload'].hex(),'240101')
        self.assertIsNone(sent(self.client,0x6a));self.assertIsNone(sent(self.client,0x08))
        with self.assertRaises(Exception) as error:await self.gimbal.setVelocity(pan=.1)
        self.assertEqual(error.exception.code,'RS4MINI_BUSY')
        reply(self.client,r,[0]);result=await task
        self.assertEqual(result['requestedValue'],1)
        self.assertFalse(result['physicalCompletionVerified'])
        self.assertIsNone(self.gimbal.activeOperation)

    async def test_invalid_action_context_and_negative_ack(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        with self.assertRaises(TypeError):await self.gimbal.appCommands.sendAutoCalibrationRequest(start=False)
        with self.assertRaises(Exception):await self.gimbal.appCommands.sendAutoCalibrationRequest(timeoutMs=0)
        self.assertEqual(self.client.frames(),[])
        task=asyncio.create_task(self.gimbal.appCommands.getAutoCalibrationStatus())
        await fixtures.until(lambda:sent(self.client,0x10));reply(self.client,sent(self.client,0x10),[0,37,1,3])
        with self.assertRaises(Exception) as error:await task
        self.assertEqual(error.exception.code,'RS4MINI_PROTOCOL_ERROR')
        task=asyncio.create_task(self.gimbal.appCommands.sendAutoCalibrationRequest())
        await fixtures.until(lambda:sent(self.client,0x0f));reply(self.client,sent(self.client,0x0f),[7])
        with self.assertRaises(Exception) as error:await task
        self.assertEqual(error.exception.code,'RS4MINI_DEVICE_ERROR')

    async def test_cancel_deadline_do_not_replay_or_invent_abort(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.appCommands.sendAutoCalibrationRequest())
        await fixtures.until(lambda:sent(self.client,0x0f));await self.gimbal.stop()
        with self.assertRaises(Exception) as error:await task
        self.assertEqual(error.exception.code,'RS4MINI_OPERATION_CANCELLED')
        with self.assertRaises(Exception) as error:await self.gimbal.appCommands.sendAutoCalibrationRequest(timeoutMs=5)
        self.assertEqual(error.exception.code,'RS4MINI_RESPONSE_TIMEOUT')
        writes=[f for f in self.client.frames() if f['commandId']==0x0f]
        self.assertEqual(len(writes),2)
        self.assertTrue(all(f['payload'].hex()=='240101' for f in writes))
        self.assertFalse(self.gimbal.experimental.pending)
