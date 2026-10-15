# Changelog

## 0.5.0

- Added TypeScript declarations for the public SDK and protocol APIs.
- Made `stop()` cancel an active `moveTo()` instead of allowing the closed loop to restart motion.
- Prevented velocity and recenter commands from racing an active `moveTo()`.
- Added configurable Pan/Tilt/Roll position examples and documented the verified live-test results.
- Removed an unsafe legacy infinite-motion test script.
- Added package contents, license, and complete offline-test metadata.

## 0.4.0

- Added `getAttitude()`, `getJointAngles()`, and feedback-driven `moveTo()`.
- Verified Pan, Tilt, and Roll joint mappings on an RS 4 Mini.

## 0.3.0

- Added DUML notification stream reassembly, CRC validation, and `04:05` telemetry decoding.
- Added cached CoreBluetooth UUID reconnection.
