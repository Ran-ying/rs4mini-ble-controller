import asyncio
import unittest
import test_controller as fixtures
from test_app_commands import reply,sent
from rs4mini_sdk.app_balance import balance_fields

class AppBalanceTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.ControllerTests.asyncSetUp
    asyncTearDown=fixtures.ControllerTests.asyncTearDown

    async def test_fields_and_zero_invalid(self):
        self.assertIsNone(balance_fields(0)['axisResults']['roll']['result'])
        result=balance_fields(0x9b)
        self.assertEqual(result['state'],'FINISH')
        self.assertEqual([r['result'] for r in result['axisResults'].values()],['PASS','MARGINAL','FAIL'])
        self.assertEqual(balance_fields(64)['state'],'TESTING')
        self.assertEqual(balance_fields(255)['state'],'ERROR')

    async def test_raw_values_and_partial_results(self):
        for value in range(256):self.assertEqual(balance_fields(value)['rawValue'],value)
        partial=balance_fields(0x90)
        self.assertEqual(partial['axisResults']['roll']['result'],'PASS')
        self.assertIsNone(partial['axisResults']['pitch']['result'])
        self.assertFalse(partial['axisFieldsValid'])
        for invalid in (256,True,-1):
            with self.assertRaises(ValueError):balance_fields(invalid)

    async def test_status_named_query_and_correlation(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.app_commands.get_balance_test_status())
        await fixtures.until(lambda:sent(self.client,0x10));r=sent(self.client,0x10)
        self.assertEqual(r['payload'],b'\x25')
        reply(self.client,dict(r,commandId=0x0f),[0]);await asyncio.sleep(0)
        self.assertFalse(task.done())
        reply(self.client,r,[0,37,9,0x9b]);result=await task
        self.assertEqual(result['balance']['state'],'FINISH')
        self.assertEqual(result['parameters'][0]['headerByte'],9)
        self.assertFalse(result['physicalCompletionVerified'])

    async def test_start_fixed_value_owns_until_ack(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.app_commands.send_balance_test_request())
        await fixtures.until(lambda:sent(self.client,0x0f));r=sent(self.client,0x0f)
        self.assertEqual(r['payload'].hex(),'250140')
        self.assertIsNone(sent(self.client,0x40))
        with self.assertRaises(Exception) as error:await self.gimbal.setVelocity(pan=.1)
        self.assertEqual(error.exception.code,'RS4MINI_BUSY')
        reply(self.client,r,[0]);result=await task
        self.assertEqual(result['requestedValue'],64)
        self.assertFalse(result['physicalCompletionVerified'])
        self.assertIsNone(self.gimbal.activeOperation)

    async def test_invalid_actions_malformed_status_and_nack(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        with self.assertRaises(TypeError):await self.gimbal.appCommands.sendBalanceTestRequest(value=0)
        with self.assertRaises(Exception):await self.gimbal.appCommands.sendBalanceTestRequest(timeoutMs=0)
        self.assertEqual(self.client.frames(),[])
        task=asyncio.create_task(self.gimbal.appCommands.getBalanceTestStatus())
        await fixtures.until(lambda:sent(self.client,0x10));reply(self.client,sent(self.client,0x10),[0,37,1])
        with self.assertRaises(Exception) as error:await task
        self.assertEqual(error.exception.code,'RS4MINI_PROTOCOL_ERROR')
        task=asyncio.create_task(self.gimbal.appCommands.sendBalanceTestRequest())
        await fixtures.until(lambda:sent(self.client,0x0f));reply(self.client,sent(self.client,0x0f),[7])
        with self.assertRaises(Exception) as error:await task
        self.assertEqual(error.exception.code,'RS4MINI_DEVICE_ERROR')

    async def test_cancel_timeout_do_not_invent_abort_or_replay(self):
        self.gimbal.appCommands.useProfile('ronin-2.2.2')
        task=asyncio.create_task(self.gimbal.appCommands.sendBalanceTestRequest())
        await fixtures.until(lambda:sent(self.client,0x0f));await self.gimbal.stop()
        with self.assertRaises(Exception) as error:await task
        self.assertEqual(error.exception.code,'RS4MINI_OPERATION_CANCELLED')
        with self.assertRaises(Exception) as error:await self.gimbal.appCommands.sendBalanceTestRequest(timeoutMs=5)
        self.assertEqual(error.exception.code,'RS4MINI_RESPONSE_TIMEOUT')
        writes=[f for f in self.client.frames() if f['commandId']==0x0f]
        self.assertEqual(len(writes),2)
        self.assertTrue(all(f['payload'].hex()=='250140' for f in writes))
        self.assertFalse(self.gimbal.experimental.pending)
