import os
import subprocess
import sys
import unittest

class DeviceBoundaryTests(unittest.TestCase):
    def test_device_can_import_without_loading_application_layer(self):
        env = dict(os.environ, PYTHONPATH=os.path.dirname(os.path.dirname(__file__)))
        code = '''import sys
from rs4mini_sdk.device import BleDevice
assert 'rs4mini_sdk.controller' not in sys.modules
assert 'rs4mini_sdk.expansion' not in sys.modules
assert 'rs4mini_sdk.experimental' not in sys.modules
assert not hasattr(BleDevice, 'moveTo')
assert not hasattr(BleDevice, 'runTrajectory')
from rs4mini_sdk import RS4Mini, RS4MiniError
from rs4mini_sdk.errors import RS4MiniError as SharedError
assert issubclass(RS4Mini, BleDevice)
assert RS4MiniError is SharedError
assert hasattr(RS4Mini, 'moveTo')
'''
        subprocess.run([sys.executable, '-c', code], check=True, env=env)

class DeviceRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_degree_info_uses_same_device_contract_from_both_entries(self):
        import asyncio
        from rs4mini_sdk import RS4Mini
        from rs4mini_sdk.device import BleDevice
        from test_controller import FakeClient, Scanner, until
        from test_experimental import incoming
        for cls in (BleDevice, RS4Mini):
            app = cls(client_factory=FakeClient, scanner=Scanner, rateHz=1000)
            try:
                await app.connect()
                request = asyncio.create_task(app.request_degree_info(timeout_ms=1000))
                await until(lambda: app.client.frames())
                sent = app.client.frames()[0]
                self.assertEqual(sent['commandId'], 0x1e)
                self.assertEqual(sent['payload'], b'')
                app.client.notify(None, incoming(sent['sequence'], 4, 0x1e, b'\0'))
                self.assertEqual((await request)['payload'], b'\0')
                self.assertIsNone(app.experimental.profile)
            finally:
                await app.close()
