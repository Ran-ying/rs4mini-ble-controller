import unittest
from unittest.mock import patch
from rs4mini_sdk.macos_device import cached_device, _bleak_device


class CachedDeviceTests(unittest.TestCase):
    def test_legacy_bleak_requires_rssi_but_cached_signal_is_unknown(self):
        class Legacy:
            def __init__(self, address, name, details, rssi):
                self.address, self.details, self.rssi = address, details, rssi
        details = object()
        device = _bleak_device(Legacy, 'cached-uuid', 'test', details)
        self.assertIs(device.details, details)
        self.assertIsNone(device.rssi)

    def test_modern_bleak_receives_no_deprecated_rssi_argument(self):
        class Modern:
            def __init__(self, address, name, details):
                self.address, self.details = address, details
        details = object()
        self.assertIs(_bleak_device(Modern, 'cached-uuid', 'test', details).details, details)

    def test_installed_bleak_constructor_accepts_cached_details(self):
        from bleak.backends.device import BLEDevice
        details = object()
        device = _bleak_device(BLEDevice, '00000000-0000-0000-0000-000000000001', 'test', details)
        self.assertIs(device.details, details)

    def test_non_macos_and_discovered_objects_never_initialize_manager(self):
        with patch('rs4mini_sdk.macos_device._retrieve') as retrieve:
            with patch('rs4mini_sdk.macos_device.sys.platform', 'linux'):
                self.assertEqual(cached_device('00000000-0000-0000-0000-000000000001'),
                                 '00000000-0000-0000-0000-000000000001')
            with patch('rs4mini_sdk.macos_device.sys.platform', 'darwin'):
                device = object()
                self.assertIs(cached_device(device), device)
                self.assertEqual(cached_device('not-a-uuid'), 'not-a-uuid')
            retrieve.assert_not_called()

    def test_known_uuid_returns_device_and_normalizes_uuid(self):
        device = object()
        with patch('rs4mini_sdk.macos_device.sys.platform', 'darwin'), \
             patch('rs4mini_sdk.macos_device._retrieve', return_value=device) as retrieve:
            self.assertIs(cached_device('00000000000000000000000000000001'), device)
            retrieve.assert_called_once_with('00000000-0000-0000-0000-000000000001')

    def test_unknown_uuid_preserves_scan_fallback_and_permission_errors_surface(self):
        address = '00000000-0000-0000-0000-000000000001'
        with patch('rs4mini_sdk.macos_device.sys.platform', 'darwin'), \
             patch('rs4mini_sdk.macos_device._retrieve', return_value=None):
            self.assertEqual(cached_device(address), address)
        with patch('rs4mini_sdk.macos_device.sys.platform', 'darwin'), \
             patch('rs4mini_sdk.macos_device._retrieve', side_effect=RuntimeError('unauthorized')):
            with self.assertRaisesRegex(RuntimeError, 'unauthorized'):
                cached_device(address)
