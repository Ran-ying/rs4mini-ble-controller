"""Resolve a cached CoreBluetooth UUID without requiring advertisements.

Only the default macOS transport uses this bridge. Bleak owns connection,
services and notifications; the SDK never writes through CoreBluetooth here.
"""
import sys
from inspect import signature
from uuid import UUID


def cached_device(address):
    if sys.platform != 'darwin' or not isinstance(address, str):
        return address
    try:
        identifier = str(UUID(address)).upper()
    except ValueError:
        return address
    return _retrieve(identifier) or address


def _retrieve(identifier):
    # Lazy imports keep Linux/Windows, pure codecs and fake clients independent
    # of PyObjC. These are the same BLEDevice details used by Bleak's scanner.
    from bleak.backends.device import BLEDevice
    from bleak.backends.corebluetooth.CentralManagerDelegate import CentralManagerDelegate
    from Foundation import NSUUID
    manager = CentralManagerDelegate.alloc().init()
    native_id = NSUUID.alloc().initWithUUIDString_(identifier)
    peripherals = manager.central_manager.retrievePeripheralsWithIdentifiers_([native_id])
    if not peripherals:
        return None
    peripheral = peripherals[0]
    return _bleak_device(BLEDevice, str(peripheral.identifier().UUIDString()),
                         peripheral.name(), (peripheral, manager))


def _bleak_device(factory, address, name, details):
    # Bleak 0.22 requires rssi; newer releases removed it. Cached retrieval has
    # no advertisement/RSSI, so do not fabricate a measured signal strength.
    kwargs = {'rssi': None} if 'rssi' in signature(factory).parameters else {}
    return factory(address, name, details, **kwargs)
