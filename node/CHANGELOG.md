# Changelog

## 0.7.0

- 显式有界自动重连，取消与耗尽状态，恢复连接后不重放运动。
- 速度关键帧插值、串行写入与迟到采样跳过；逐点关节目标与停留。
- 保存位置与选轴返回；要求显式分量顺序的四元数数学转换。
- 独立研究配置：原生角度/速率、休眠/唤醒、限定请求响应及被动状态。
  所有新协议仍未在 RS 4 Mini 上实测；原生面板与网页已接入新入口，可视界面和硬件效果待统一验证。

## 0.6.0

- Added operation ownership through final neutral writes; `stop()` now waits for cancelled motion cleanup, and duration sleeps are cancellable.
- Zeroed individual axes inside position tolerance and normalized total move timeout errors, including telemetry waits.
- Bounded power, scan start/stop, cached/peripheral connect, discovery and subscription; cancelled and cleaned up late connection results.
- Gave default controllers independent lazy Noble backends and owned power-state listeners, so cancelling a powered-off connection does not leave a long-lived timeout.
- Removed stale notification/disconnect listeners, isolated synchronous/asynchronous callbacks, and exposed copied telemetry/velocity state.
- Added per-write deadlines, complete-frame serialization before neutral frames, and disconnect-on-write-failure behavior.
- Shared the pure controller/protocol/telemetry core with Web Bluetooth while preserving Node Buffer exports.
- Added deterministic failure-path tests and expanded consumer type checks. New motion behavior requires separate hardware validation.

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
