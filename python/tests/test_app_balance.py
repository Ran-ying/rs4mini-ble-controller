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
