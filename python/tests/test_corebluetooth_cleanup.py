import unittest
from unittest.mock import patch
from rs4mini_sdk import RS4Mini
from test_controller import FakeClient, Scanner


class CoreBluetoothCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_macos_disconnect_never_writes_notification_disable(self):
        class Client(FakeClient):
            async def stop_notify(self, characteristic):
                raise AssertionError('unexpected notification-disable write')
        with patch('rs4mini_sdk.device.sys.platform', 'darwin'), \
             patch('rs4mini_sdk.device.BleakClient', Client), \
             patch('rs4mini_sdk.device.cached_device', side_effect=lambda address: address):
            g = RS4Mini(scanner=Scanner)
            await g.connect()
            client = g.client
            await g.close()
            self.assertEqual(client.disconnects, 1)
            self.assertFalse(client.is_connected)
            self.assertFalse(g.connected)
            self.assertTrue(g.closed)
            client.telemetry(yaw=12)
            self.assertIsNone(g.latestTelemetry)

    async def test_macos_real_disconnect_failure_still_propagates(self):
        class Client(FakeClient):
            async def disconnect(self):
                raise RuntimeError('disconnect failed')
        with patch('rs4mini_sdk.device.sys.platform', 'darwin'), \
             patch('rs4mini_sdk.device.BleakClient', Client), \
             patch('rs4mini_sdk.device.cached_device', side_effect=lambda address: address):
            g = RS4Mini(scanner=Scanner)
            await g.connect()
            with self.assertRaisesRegex(RuntimeError, 'disconnect failed'):
                await g.close()
            self.assertFalse(g.connected)
            self.assertTrue(g.closed)

    async def test_injected_clients_keep_explicit_unsubscribe_errors(self):
        class Client(FakeClient):
            async def stop_notify(self, characteristic):
                raise RuntimeError('unsubscribe failed')
        with patch('rs4mini_sdk.device.sys.platform', 'darwin'):
            g = RS4Mini(scanner=Scanner, client_factory=Client)
            await g.connect()
            client = g.client
            with self.assertRaisesRegex(RuntimeError, 'unsubscribe failed'):
                await g.close()
            self.assertEqual(client.disconnects, 1)
            self.assertTrue(g.closed)

    async def test_other_platform_default_keeps_explicit_unsubscribe(self):
        with patch('rs4mini_sdk.device.sys.platform', 'linux'):
            g = RS4Mini()
            self.assertTrue(g._unsubscribe_before_disconnect)
            await g.close()
