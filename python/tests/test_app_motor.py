import asyncio
import unittest
import test_controller as fixtures
from test_app_commands import reply,sent


class AppMotorTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.ControllerTests.asyncSetUp
    asyncTearDown=fixtures.ControllerTests.asyncTearDown

    async def test_motor_namespace_and_full_context(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.app_commands.get_motor_tuning())
        await fixtures.until(lambda:sent(self.client,0x32))
        request=sent(self.client,0x32)
        self.assertEqual(request['payload'],bytes(range(12)))
        reply(self.client,dict(request,commandId=0x10),[0,0,1,50])
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        payload=[0]
        for index in range(12):payload.extend((index,9,255 if index==0 else index))
        reply(self.client,request,payload)
        result=await task
        self.assertEqual(len(result['values']),12)
        self.assertEqual(result['values'][0]['rawValue'],255)
        self.assertFalse(result['values'][0]['withinSourceRange'])
        self.assertEqual(result['values'][11]['parameter'],'preControl')
        self.assertEqual(result['values'][11]['axis'],'yaw')

    async def test_filtered_query_uses_distinct_named_fields(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.appCommands.getMotorTuning(axis='yaw'))
        await fixtures.until(lambda:sent(self.client,0x32))
        request=sent(self.client,0x32)
        self.assertEqual(request['payload'].hex(),'0205080b')
        reply(self.client,request,[0,2,1,20,5,1,30,8,1,0,11,1,100])
        self.assertEqual([r['axis'] for r in (await task)['values']],['yaw']*4)

    async def test_named_write_waits_for_ack_in_motor_namespace(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.app_commands.set_motor_tuning(axis='roll',parameter='stiffness',value=50))
        await fixtures.until(lambda:sent(self.client,0x31))
        request=sent(self.client,0x31)
        self.assertEqual(request['payload'].hex(),'010132')
        with self.assertRaises(Exception) as busy:await self.gimbal.setVelocity(pan=.1)
        self.assertEqual(busy.exception.code,'RS4MINI_BUSY')
        reply(self.client,request,[0])
        result=await task
        self.assertEqual(result['requestedValue'],50)
        self.assertFalse(result['physicalCompletionVerified'])
        self.assertIsNone(sent(self.client,0x0f))

    async def test_invalid_fields_do_not_send_or_stop(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        for spec in [dict(axis='pitch',parameter='stiffness',value=4),dict(axis='yaw',parameter='strength',value=0),dict(axis='roll',parameter='gyroFiltering',value=101),dict(axis='pitch',parameter='preControl',value=True),dict(axis='pan',parameter='stiffness',value=50)]:
            with self.assertRaises(ValueError):await self.gimbal.appCommands.setMotorTuning(**spec)
        with self.assertRaises(TypeError):await self.gimbal.appCommands.getMotorTuning(index=0)
        self.assertEqual(self.client.frames(),[])

    async def test_truncated_and_rejected_queries_cleanup(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        for payload,code in [([0,0,1],'RS4MINI_PROTOCOL_ERROR'),([7],'RS4MINI_DEVICE_ERROR')]:
            count=len(self.client.frames())
            task=asyncio.create_task(self.gimbal.appCommands.getMotorTuning(axis='pitch',parameter='stiffness'))
            await fixtures.until(lambda:len(self.client.frames())>count)
            reply(self.client,sent(self.client,0x32),payload)
            with self.assertRaises(Exception) as error:await task
            self.assertEqual(error.exception.code,code)
        self.assertFalse(self.gimbal.experimental.pending)

    async def test_write_cancel_timeout_no_replay(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.appCommands.setMotorTuning(axis='yaw',parameter='gyroFiltering',value=0))
        await fixtures.until(lambda:sent(self.client,0x31))
        await self.gimbal.stop()
        with self.assertRaises(Exception) as cancelled:await task
        self.assertEqual(cancelled.exception.code,'RS4MINI_OPERATION_CANCELLED')
        with self.assertRaises(Exception) as timeout:await self.gimbal.appCommands.setMotorTuning(axis='pitch',parameter='preControl',value=100,timeoutMs=5)
        self.assertEqual(timeout.exception.code,'RS4MINI_RESPONSE_TIMEOUT')
        self.assertFalse(self.gimbal.experimental.pending)
        self.assertEqual(len([r for r in self.client.frames() if r['commandId']==0x31]),2)
