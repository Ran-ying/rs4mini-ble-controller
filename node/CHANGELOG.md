# Changelog

## 0.7.3

- 显式 `ronin-2.2.2` 设备接口：参数上下文读取、HG724 跟随灵敏度0/1读写；同步 Python、共享 Web、原生0.3.3。
- 旧研究配置互斥；复用连接/队列/序号/操作槽。返回码与高索引分离，保留原始宽值、头字节和未知 ACK 尾部。
- 写入等待严格关联 ACK，覆盖取消、超时、断连和迟到回复；不重放。未操作硬件，ACK不表示物理效果。
- 固定恢复视图的命令方法指纹审计；全协议和高级开发条件仍未通过。

## 0.7.2

- 补充显式研究配置中的被动用户参数响应/ACK 解析：原始值、返回码、逐项错误和重复索引；严格检查长度与响应位。
- Python/Web/原生同步；不新增参数查询/写入接口或高级功能，结果仍标记本机未验证。
- 增加可复现的官方 APK 静态元数据研究工具和事实摘要，扩充候选命令审计；关键方法仍为保护桩，全命令条件未满足。

## 0.7.1

- 分离设备 SDK 与高级应用入口；保持现有 API、单连接/队列及停止取消契约。
- Node/Web 共享分层核心；Python 与原生同步拆分，底层可独立加载/链接。
- 补入 `04:1E` 的 `requestDegreeInfo()` 关联原始响应接口，不宣称提高反馈频率。
- 新增机器命令清单、分层 CI 检查及底层独立运行测试；底层命令完整性仍未验收，不新增高级功能。

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
