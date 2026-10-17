# Changelog

## 0.7.11

- 四端新增get/setStandaloneTuning与Python别名：六个独立配置数值，调用方必须显式选择输入源2，与数值同包写入0F并独占至ACK。
- 读取10包含实际输入源与选定值，保留未知原值；不自动选路、切预设、重放或回滚，不增加高级任务。
- 固定六个HG724条件分支方法指纹，并逐项比对三端参数目录；本机效果、持久化及全部命令仍未验收。

## 0.7.10

- 修复轨迹超时测试的真实调度时序依赖：可控时钟分别验证首次调度前超时仅三帧中位停止，以及慢写后超时一帧运动加三帧停止，不改变运行时运动逻辑。

- 同步四端get/setFollowTuning与get/setRcTuning：18项普通命名数值按外部元数据宽度读写，保留小端无符号异常原值与withinSourceRange标记。
- 单项写入严格源码整数范围、独占到ACK、可取消且无重放；不自动切档位、活动预设或输入源，activePresetVerified明确false。
- 三端目录逐项与源码证据比对，补齐混合宽度/错误命令/取消/异常ACK测试。无硬件/UI或高级新增，独立配置与全部协议仍未完成。

## 0.7.9

- 四端新增六组跟随/RC参数按轴档位读取与读改写，绑定六个命名资源，不开放整字节或任意索引写入。
- Pitch/Roll/Yaw使用bits2..3/4..5/6..7，custom/low/middle/high为0/1/2/3。新鲜读取保留未指定轴和低两位，整个事务独占、单截止时间、可取消无重放。
- 核对SDK/UI跨段18方法指纹，覆盖参数复制、畸形响应、保留位和取消/超时。无硬件/UI/高级新增；PF/PTF等预设及实机验收仍未完成。

## 0.7.8

- 四端新增system_calc自动校准固定请求与状态读取；普通0F/10/index36，与6A/6E自动调参分开。
- 状态枚举0..3独立于写入范围0..1，未知值保留raw/null。启动等待ACK、可取消且不重放，不推断中止/物理完成或水平校准身份。
- 静态复现14方法指纹与实际数组槽；离线验证命令关联、错误/未知状态、互斥及清理。无硬件/UI操作或高级新增。

## 0.7.7

- 同步四端平衡测试启动请求sendBalanceTestRequest和getBalanceTestStatus，固定04:0F启动64、04:10命名读取，保留零结果字段为null。
- 启动独占到ACK，超时/取消不重放、不发虚构中止；状态不与本机请求关联，ACK和FINISH不当作物理完成证据。
- 离线覆盖命令隔离、原值保留、畸形响应、互斥和清理。没有硬件/UI操作或高级新增。

## 0.7.6

- 显式当前App配置新增getMotorTuning/setMotorTuning，封装三轴刚度/强度/陀螺仪滤波/PreControl十二个命名字段；同步Python/Web/原生SDK。
- 31/32电机空间与0F/10分开，来源按名字追踪；查询依赖显式元数据，保留未知读值，单项写入校验源范围、独占操作槽并等待关联ACK，取消/超时无重放。
- 补齐INT08U、打包switch和低字节顺序证据，共26个方法指纹。范围不代表机械安全，设备效果/持久化未验证；未操作硬件或增加高级任务。

## 0.7.5

- 按HG724继承的HG702覆盖路径封装04:6A无ACK自动调参请求，严格布尔动作，发送结果不宣称设备确认或物理完成。同步Python/Web/原生SDK。
- 04:6E空体查询与被动记录解析分开，支持当前App状态枚举，保留未知字段/原值；空ACK不造零进度，查询不污染推送缓存，切换配置/断连清理。
- 覆盖背压发送、取消、迟到响应、观察者异常、跨端类型与无Buffer环境。固定当前App方法/枚举证据。
- 没有硬件操作或高级新增；全命令与物理效果验收仍未完成。

## 0.7.4

- 显式当前App配置新增自定义跟随与电机设置的命名位字段读写；同步四端SDK，不新增高级运动功能。
- 按刚读到的值修改指定字段，保留其余位；电机启用位反向，未知自定义位拒绝写入。读/写共享单调时钟总截止时间和操作槽，取消/读失败不继续写，不自动重发。
- 固定八个setter掩码/极性、继承链和两条命名参数的静态证据；本机效果尚未验证，完整性门槛仍false。

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
