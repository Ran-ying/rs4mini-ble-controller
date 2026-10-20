# RS4 Mini Node API

> 0.7.39 / macOS0.3.40 build43：已按用户要求移除实验区position查询和六类未验收状态的公开属性、缓存、事件及GUI显示；保留四类已实测状态。以下旧版本记录为历史。详见[本轮清理](../docs/SDK_UNVERIFIED_REMOVAL.md)。

> 0.7.38 / macOS0.3.39：用户要求移除旧system_calc和旧平衡测试的启动/状态共4个公开方法，三端及GUI同步。保留已实测的电机自动调参、AUTO水平校准、Pitch/Roll手动微调。绿色平衡状态读取未实现；不计作当前SDK能力。详见[逐项验收](../docs/SDK_ACCEPTANCE_QUEUE.md)。


> 当前变更：用户已要求移除参数/程序连续订阅、手柄/摇杆写入和恢复设置的公开SDK入口及GUI动作。下文相关旧版本描述为历史；被动状态和程序状态单次查询保留。本机已确认AUTO对应水平校准，Roll对应手动水平微调；旧system_calc与平衡测试无反应，完整验收尚未完成。


## 当前变更：0.7.36

`getHandleSettings()`与`queryCalibrationStatus()`已移除；使用被动`calibrationStatus`观察已有通知，不把缓存当主动查询。Python相应别名和原生查询selector同步移除。

`getMotorTuning()`默认逐项请求12个参数，按轴4项、按参数3项。单项返回原AppParameterReply加`readMode:'single'`；多项返回`readMode:'sequential',atomic:false,values,parameters,replies`，每个replies元素都是本次真实单项响应。多项顶层没有message/bodyHex/statusCode合成ACK；需要原始报文时读取各replies。总timeoutMs覆盖整个读取循环，取消/失败不返回部分数据，不发余下请求。多项独占操作槽并停止原连续主机运动，单项保持已有有限查询语义。详见[电机接口](../docs/APP_MOTOR_TUNING.md)。下文旧版本入口记录为历史。

`RS4Mini` 是应用唯一入口；0.7.1 已将其下的设备 SDK 与电脑端组合运动拆成模块。
基础操作继承自设备 SDK，高级方法使用同一个设备连接和操作协调器。
`setVelocity()`、三轴 `recenter()` 与反馈读取封装设备协议；`moveTo()`、`moveFor()`、
轨迹、路点、保存位置返回是主机算法，不能作为设备具备同名原生命令的证据。
完整归属和停止协作契约见 [架构边界](../docs/ARCHITECTURE.md)。

所有公共方法均为异步方法。除读取缓存状态外，请在调用前完成 `await gimbal.connect()`。

## `new RS4Mini(options?)`

```ts
type ControllerOptions = {
  nameIncludes?: string; // 默认 "DJI RS4 MINI"
  rateHz?: number;       // 默认 15，仅为命令发送频率
  ioTimeoutMs?: number;  // 默认 3000，每次 GATT 写入/清理截止时间
  deviceId?: string;     // 缓存的 macOS CoreBluetooth UUID
};
```

## 连接生命周期

| 方法 | 返回 | 说明 |
|---|---|---|
| `connect(options?)` | `Promise<string>` | 直接连接缓存 UUID，失败时自动扫描 |
| `disconnect()` | `Promise<void>` | 停止、断开；实例仍可再次连接 |
| `close()` | `Promise<void>` | 停止、断开并关闭 Noble；实例不可复用 |

`connect()` 选项：

```ts
type ConnectOptions = {
  timeoutMs?: number;              // 默认 30000
  directConnectTimeoutMs?: number; // 默认 5000
  deviceId?: string;
};
```

`timeoutMs` 覆盖等待蓝牙、扫描启停、直连、外设连接、GATT 发现和通知订阅。
超时或取消立即使连接尝试失效，异步清理和迟到结果不会重新发布已关闭连接。
操作系统清理可在拒绝之后继续，单次清理由 `ioTimeoutMs` 限制。
`disconnect()` 和 `close()` 可以取消尚未完成的连接。每个控制器独占其适配器，
默认各实例使用独立的惰性 Noble 后端；注入同一个自定义适配器时，不要并发使用多个控制器。

## 运动控制

### `setVelocity(options?)`

持续发送标准化虚拟摇杆速度，范围 `-1…+1`。未提供的轴为零。

```js
await gimbal.setVelocity({ pan: 0.25, tilt: -0.1, roll: 0 });
await gimbal.stop();
```

### `setVelocityDeg(options?)`

按经验满量程换算近似角速度。它不是编码器闭环速度控制。

```js
await gimbal.setVelocityDeg({
  pan: 10,
  tilt: 5,
  roll: 2,
  panFullScale: 37.5,
  tiltFullScale: 27.5,
  rollFullScale: 30,
});
```

### `moveFor(options)`

```js
await gimbal.moveFor({ pan: 0.3, tilt: 0, roll: 0, durationMs: 800 });
```

到时或发生异常都会尝试停止。`stop()` 能立即唤醒该时长等待；旧操作的睡眠到期后
不会再停止新运动。取消时以 `RS4MINI_MOVE_CANCELLED` 拒绝。

### `moveTo(options)`

使用关节角反馈进行低速位置闭环：

```js
const result = await gimbal.moveTo({
  pan: 20,             // Joint Yaw
  tilt: 5,             // Joint Pitch
  roll: -3,            // Joint Roll
  toleranceDeg: 1,
  timeoutMs: 30_000,
  telemetryTimeoutMs: 3000,
  gain: 0.02,
  minSpeed: 0.05,
  maxSpeed: 0.18,
});
```

至少指定一个目标轴，目标范围为 `-180°…+180°`。返回：

```ts
{
  target: { pan?: number; tilt?: number; roll?: number };
  current: { pan: number; tilt: number; roll: number };
  error: { pan: number; tilt: number; roll: number };
  toleranceDeg: number;
  elapsedMs: number;
}
```

并发规则：

- 任一有限运动、初次速度写入、回中与最后停止清理期间，其他运动以 `RS4MINI_BUSY` 拒绝；
- 调用 `stop()` 会取消命令流与等待，并使进行中的 `moveTo()` 或 `moveFor()` 以
  `error.code === "RS4MINI_MOVE_CANCELLED"` 结束；
- 位置总超时统一使用 `error.code === "RS4MINI_MOVE_TIMEOUT"`，并附带
  `target` 和 `current`（无样本时为 `null`）。单帧反馈先超时则为 `RS4MINI_TELEMETRY_TIMEOUT`。

`stop()` 等待旧操作清理结束后返回；调用方仍应为旧运动 promise 安装拒绝处理。
多轴定位每个已进入容差的轴单独归零，直到全部到位。手动连续速度可以在上一次
`setVelocity()` 返回后更新；新位置/限时操作会先停止旧连续速度。

### `stop()` 与 `recenter()`

`stop()` 停止命令流并连续发送三个全轴中位帧。已开始的 DUML 帧先完成 20 字节分片；
尚未开始的过期运动帧被丢弃。每次写入超时或失败会断开连接，避免拼接破损帧。
`recenter()` 先停止，再执行 DJI 的三轴回中；
当前没有单轴回中。

## 反馈读取

### `getAttitude(options?)`

返回姿态 `pitch/roll/yaw`。这是方向姿态，不是机械轴角度。

### `getJointAngles(options?)`

返回机械关节 `pitch/roll/yaw`。控制轴映射为：

```text
pan  = yaw
tilt = pitch
roll = roll
```

两个读取方法的选项相同：

```ts
{
  fresh?: boolean;    // false：优先缓存；true：等待下一帧
  timeoutMs?: number; // 默认 3000
}
```

返回对象包含角度、`unit: "deg"`、原始整数值和毫秒时间戳。

## 状态与回调

| 成员 | 类型/用途 |
|---|---|
| `connected` | 是否连接 |
| `deviceName` | 当前设备名称 |
| `deviceId` | CoreBluetooth UUID，可跨进程保存 |
| `velocity` | 当前标准化三轴速度 |
| `latestTelemetry` | 最近一次完整遥测或 `null` |
| `moveToActive` | 位置闭环是否正在运行 |
| `activeOperation` | 当前初次速度写入、限时运动、位置、回中或停止；空闲时 `null` |
| `onNotification` | 原始 FFF4 BLE 通知块 |
| `onMessage` | CRC 校验后的完整 DUML 消息 |
| `onTelemetry` | 解码后的 `04:05` 反馈 |
| `onDisconnect` | 意外或主动断开通知 |
| `onError` | 后台运动流写入错误 |

完整 TypeScript 类型由 `src/index.d.ts` 随包提供。

`velocity`、`latestTelemetry`、读取返回值与回调参数为副本。回调支持同步/异步函数，
异常传给 `onError`，不会中断解码；`onError` 自身异常被隔离。

## 错误与清理

`RS4MINI_BUSY`、`RS4MINI_OPERATION_CANCELLED`、`RS4MINI_MOVE_CANCELLED`、
`RS4MINI_MOVE_TIMEOUT`、`RS4MINI_TELEMETRY_TIMEOUT`、`RS4MINI_CONNECT_TIMEOUT`、
`RS4MINI_CONNECT_CANCELLED`、`RS4MINI_IO_TIMEOUT`、`RS4MINI_DISCONNECTED` 可通过
`error.code` 区分。适配器自己的异常保留原错误。若主操作和最终停止同时失败，主错误保留，
停止错误附在 `cleanupError`。连接尝试超时与失败不改变设备持久设置；断线不会恢复旧运动。
蓝牙不受支持或被拒绝时，Node 后端还会返回 `RS4MINI_BLUETOOTH_UNAVAILABLE`。

## 0.7.0 非相机扩展

`getOrientation({componentOrder:'wxyz',conjugate:false,fresh:true})` 要求调用方显式指定
四个浮点分量的顺序。也可选 xyzw；返回归一化 quaternion、标准右手内禀 ZYX 欧拉角、
输入模长及 `deviceConventionVerified:false`。原始模长偏离 1 超过 normTolerance（默认 0.1）
时拒绝，短帧不会满足等待。纯函数 `orientationFromComponents()` 适用于离线数学转换。
分量顺序、物理坐标方向和参考系仍需实测；转换结果不用于 `moveTo()`，也不自动替代姿态字段。

`enableAutoReconnect({maxAttempts:5, initialDelayMs:500, maxDelayMs:10000,
backoff:2, timeoutMs:10000, directConnectTimeoutMs:5000})` 为后续意外断线启用有界重试。
不会主动连接当前未连接的设备；初次仍调用 `connect()`。`onReconnect(state)` 报告
idle/waiting/connecting/restored/exhausted，`reconnectState` 为副本。重连只恢复链路，
速度、轨迹和等待中的操作均不恢复。手动 `disconnect()`、`close()` 或
`await disableAutoReconnect()` 取消重试；需要重新启用策略后才会再自动重连。

`runTrajectory([{timeMs:0,pan:0.05},{timeMs:1000,pan:0.1},
{timeMs:2000,pan:0}], {interpolation:'smoothstep',maxLagMs:500})` 执行归一化速度关键帧。
时间从零开始且严格递增，省略轴为零，轴值必须在 -1..1。支持 linear、smoothstep、step。
调度使用单调时钟及 `rateHz`，每帧串行完成写入；延误的采样点跳过，不能突发补发。
超过 `maxLagMs` 的调度/写入延误报 `RS4MINI_TRAJECTORY_OVERRUN` 并停止。
到最后时间自动停止，不保持末帧速度。返回发送帧数、跳过帧数与实际用时。
这是开环速度轨迹，不保证实际角度或速度精度，也不会提高硬件反馈频率。

`moveThrough([{pan:5,holdMs:1000},{pan:0}], settings)` 在一个运动所有权内逐点定位、
停止、停留；`settings` 为 `moveTo` 的控制参数，`timeoutMs` 分别限制每个路点。
这是逐点到位流程，不是连续定时角度插值。`trajectoryProgress` 返回进度副本；
停止、断线或错误取消整条流程，`stop()` 返回后旧路点不得再启动。

`await captureHome({fresh:true})` 保存当前机械关节位置；
`await moveHome({axes:['pan']})` 仅把指定轴返回此位置，默认全部轴。
保存位置绑定设备 ID，仅保存在实例内；`home` 为副本。它与固件 `recenter()` 的零点不同，
不能据此声称已经实现固件单轴回中。上述运动共用互斥、取消与三帧停止清理。

### 实验协议接口

`gimbal.experimental.useProfile('rs3')` 或 `'rs3mini'` 显式选择其他型号的研究配置。
它不是 RS 4 Mini 支持声明，不在连接时自动启用。普通 `moveTo()` 不依赖这些命令。

- `query({kind:'version'|'controlStatus'|'type',timeoutMs:3000})` 发送限定查询，
  只匹配同一连接、sequence、反向端点、命令与响应位；返回原始完整消息。
  超时为 `RS4MINI_RESPONSE_TIMEOUT`，断线取消等待。允许与运动并行，未识别的命令不能借此发送。
- `setSleep({asleep:true})` 先停止，再发送对应型号的休眠/唤醒字节；仅确认软件写入完成。
- `absolute({pan:2,parameterByte:20,observeMs:3000})` 仅 rs3 配置支持，省略轴按研究掩码禁用。
  parameterByte 是原始字节，其单位不假定为时间；observeMs 是本地占用运动槽的观察时长。
  不能把此命令目标当作机械关节角，也不能把函数返回当作到位证明。
- `rateFor({pan:2,durationMs:500})` 仅 rs3 配置支持；速率采用研究中的度/秒映射，
  最大允许绝对值 360，时长上限 60 秒。停止先发送原生零速/释放，再发普通中位帧。
- `experimental.status` 保留被动收到的休眠、校准进度、电量原始量和状态 TLV 的副本；
  `onExperimentalStatus` 通知更新。电量百分比只在 rs3mini 的 21 字节研究格式下解释，
  rs3 的第四原始量不套用未经本机验证的百分比公式。断线清空状态。

全部实验结果带 `deviceVerified:false`；写入结果还带 `physicalCompletionVerified:false`。
本机固件是否执行、轴顺序和符号、停止能否打断固件自身动作，均需统一实机验证。
协议来源及已知差异见 `../docs/PROTOCOL.md`。本轮没有发送这些命令。

## 0.7.1 设备命令审计与维护入口

应用继续 `import { RS4Mini } from 'rs4mini-sdk'`，所有基础/高级操作均经该入口。
`import { BleDevice } from 'rs4mini-sdk/device'` 是独立设备模块的维护/协议验收入口，不提供 `moveTo()`、轨迹或保存位置。

`await gimbal.requestDegreeInfo({timeoutMs:3000})` 发送已有探针证据的 `04:1E` 空负载请求，
匹配连接、sequence、端点、命令与响应位，返回 `DumlMessage`。不需要选择其他型号配置；
它不承诺反馈增频，不把历史单字节 `00` 扩大解释为完整字段语义。Python 支持同名方法与 snake_case 别名；
原生入口同名方法是回调式，独占操作槽并通过 `messageHandler` 提供原始消息，当前固定 3 秒响应等待。

完整设备命令前置验收尚未通过，已知缺口见 `../docs/SDK_COMMANDS.md`；当前不再新增高级功能。

## 0.7.2 被动参数研究状态

在已显式选择 rs3/rs3mini 研究配置的状态通道中，新增：

- `kind:'user-parameters'`：`statusCode`、`parameters` 数组；值项为 `{index,size,rawHex}`，
  旧格式的逐项错误为 `{errorCode}`。保留重复项和 8 字节原始值，不转换为可能失真的 JS 数字。
- `kind:'user-parameter-ack'`：单字节参数 ACK 的原始 `statusCode`。

两者均含 `layoutSource:'legacy-duml'`、`deviceVerified:false`；不按索引推断唯一参数名称，
不代表本机命令支持或物理执行确认。仅被动解析，不新增任何发送方法或更改发送允许列表。
Python/Web/原生提供对应状态。协议来源与保护桩边界见 `docs/PROTOCOL.md` 和 `docs/RESEARCH_NEXT.md`（仓库根目录）。


## 0.7.3 当前 App 参数设备接口

同一个 `RS4Mini.appCommands` 显式选择 `ronin-2.2.2` 来源，提供 `readParameters()`、`getFollowSensitivity()`、`setFollowSensitivity()`。与旧 experimental 配置互斥；参数、返回码、停止/查询并发和硬件边界见 [APP_COMMANDS.md](../docs/APP_COMMANDS.md)。属于设备 SDK，本机兼容和效果未验证。


0.7.4 新增显式当前App来源的自定义跟随与电机设置位字段读取/修改；保留其他位、共享事务截止时间和操作槽。入口及未验收边界见 [命名设置SDK](../docs/APP_SETTINGS.md)。


0.7.5 封装当前型号路径的无ACK自动调参请求、校准状态查询/通知，严格区分本机写入、设备报告与物理完成。接口和待验收边界见 [调参请求与状态](../docs/APP_CALIBRATION.md)。


0.7.6新增十二个命名电机数值参数的31/32读写，和普通用户参数命令空间分开；源码范围与实际设备效果分别验收。见 [电机参数SDK](../docs/APP_MOTOR_TUNING.md)。


0.7.7（原生0.3.7）新增平衡测试启动请求和状态/三轴结果读取，应用统一入口和显式当前App配置不变。接口、端差异和固件停止/完成未验收边界见 [APP_BALANCE_TEST.md](../docs/APP_BALANCE_TEST.md)。


0.7.8（原生0.3.8）新增sendAutoCalibrationRequest/getAutoCalibrationStatus及各端等价接口，与6A/6E自动调参分开。完整API、端差异和未验收边界见 [APP_SYSTEM_CALIBRATION.md](../docs/APP_SYSTEM_CALIBRATION.md)。


0.7.9（原生0.3.9）新增get/setFollowSettings与get/setRcSettings及各端等价接口：六组参数按轴custom/low/middle/high档位，先读后改写，保留其他轴和低两位。接口与未验收边界见 [APP_FOLLOW_MODES.md](../docs/APP_FOLLOW_MODES.md)。


0.7.10（原生0.3.10）新增get/setFollowTuning与get/setRcTuning及各端等价接口：18项普通命名数值、1/2字节小端、异常读值保留，不自动切档位/预设/输入源。接口与未验收边界见 [APP_NUMERIC_TUNING.md](../docs/APP_NUMERIC_TUNING.md)。


0.7.11（原生0.3.11）新增getStandaloneTuning/setStandaloneTuning，Python另有snake_case别名。六项独立配置必须显式inputSource:2，并与数值同包写入；读取保留实际输入源，无自动切换/重放/回滚，活动预设和实机效果未验收。见 [APP_STANDALONE_TUNING.md](../docs/APP_STANDALONE_TUNING.md)。


0.7.12（原生0.3.12）新增固定04:24被动用户参数缓存，17个源码getter原值，显式App配置、至少74字节、请求型且未加密；不发订阅或改变姿态反馈。onAppStatus按kind区分calibration/userParameters。接口与本机未验收边界见 [APP_USER_PARAMETERS.md](../docs/APP_USER_PARAMETERS.md)。


0.7.13（原生0.3.13）新增getHandleSettings及Python别名/原生等价接口，显式App来源下04:36空体只读查询，8个业务字段保留原值和源bit0、尾字节保留；不写入或推断profile等价关系。见 [APP_HANDLE_SETTINGS.md](../docs/APP_HANDLE_SETTINGS.md)。


0.7.14（原生0.3.14）新增sendFineTuneRequest及Python别名/原生等价方法，显式App配置、Pitch/Roll、adjustmentDegrees有限-2..2，按float32编码并独占到ACK；不声明实际角度/累加或暂停状态，也不自动暂停/回滚。见 [APP_FINE_TUNE.md](../docs/APP_FINE_TUNE.md)。


## 0.7.15手柄单字段请求 / 原生0.3.15 build18

四端设备SDK的sendHandleSettingRequest（Python snake别名）显式App来源下仅接受dualChannelMode/tiltDirection/panDirection单字段及整数0/1，8字节35体未指定字节为源默认FF。新对象/独立体，不全量读改写、不新增相机字段。参数停止前验证/快照，复用连接/队列/操作所有权至关联ACK；取消/超时无重放或回滚，NACK直接失败、不缓存兜底成功、不自动回读。结果unspecifiedByteSemanticsVerified/readbackVerified/persistenceVerified及既有设备/物理标志均false。FF实际含义、模式/方向效果、持久化待本机验收。见docs/APP_HANDLE_WRITE.md；没有高级新增或硬件操作，全部命令门槛仍false。


## 0.7.16恢复设置请求 / 原生0.3.16 build19

四端sendFactorySettingsResetRequest（Python snake别名）需显式App来源和sourcePlatform HG724，固定04:13/010001；不是类型枚举103或其他平台空体。停止前验证/快照，复用连接/队列/操作槽至关联ACK。取消/超时/断线不重发、不自动保存/回读/回滚，重连不重放。ACK不证明恢复范围、持久化、重启或物理完成，相关标志false，不自动清零/改写反馈或参数。恢复范围也未证明仅非相机字段。68方法审计新增成功/失败回调，未解析完成。见docs/APP_FACTORY_RESET.md。没有硬件/liveUI/厂商执行或高级新增；全部命令仍未完成。


## 0.7.17轴模式34读写 / 原生0.3.17 build20

四端getAxisMode/sendAxisModeRequest（Python snake别名）在显式App来源下封装34/size1。四个源枚举写0/8/16/24，读(raw>>3)&3，保留raw/unknownBits=raw&0xe7及headerByte，modelLayout/activePreset/device/physical标志false。HG724 UI只定位ThreeAxis及ThreeDRoll360，不宣称全部四种固件支持。源setter整字节写，不擅自RMW或保留其他位，otherBitsPreservationVerified/persistenceVerified=false。参数快照、写先停主机运动并独占至ACK，取消/超时/断线无重放/回滚，NACK不缓存兜底；不自动写132、17/18/19、35或激活预设，不是完整跟随模式。Node/Python有限读并发与原生读占槽差异保留。见docs/APP_AXIS_MODE.md；未操作硬件/执行厂商代码/新增高级任务，全命令未完成。


## 0.7.18普通跟随轴开关 / 原生0.3.18 build21

四端getSmoothTrackAxes/sendSmoothTrackAxesRequest（Python snake别名）显式App来源下封装17/18/19、size1，默认读三轴/可过滤单轴，写非空命名布尔子集，一条0F按yaw/pitch/roll排序，未指定字段省略。源App直接参数数组路径已确认，本次未定位逐轴SDK setter；不将其不存在或本机支持当结论。读raw0/1→enabled false/true，其他→null，保留raw/header、sourceEnabled=(raw==1)与withinSourceRange，不按bit0或错误码丢值。参数快照/写先停/独占至ACK，取消/超时/断线无重放/回滚，重连不恢复请求；不自动写132/34/35/预设/输入源/保存，不是完整模式。atomicApplication/activePreset/modelLayout/device/physical/persistence相关标志false。见docs/APP_SMOOTH_TRACK.md；没有高级新增、硬件/厂商执行，全命令仍未完成。


## 0.7.19配置0与工作模式62 / 原生0.3.19 build22

四端getUserProfile/sendUserProfileRequest、getWorkMode/sendWorkModeRequest（Python snake别名）显式App来源下独立读写0/62、size1。配置源范围0..5，源UI名仅0/1/2=M1/M2/M3，其他不推断运动预设；工作写仅精确Free/Flower/Fpv/Center四枚举，读取未知128/255保留raw并sourceMode=null、范围标志分别true/false。索引0不是空请求。与MovementSettingsProfile、推送preset、34/17-19/132等域分开，不自动组合模式或激活其他配置。写前验证/快照/停主机运动、独占至ACK，取消/超时/断线不重放/回滚/保存/读回，重连不重放，NACK不缓存兜底。modelLayout/activePreset/device/physical/persistence相关标志false，见docs/APP_PROFILE_VALUES.md。41方法源审计补充原始整数/枚举匹配与value访问器，未操作硬件、执行厂商代码或新增高级功能，全命令仍未完成。


0.7.20新增[手柄状态被动候选](../docs/APP_HANDHELD_STICK.md)，仅显式App来源、无58发送/订阅，真实57布局、单位与轴映射等待本机验收；未新增高级功能。


0.7.21新增[异常与电量被动候选](../docs/APP_SOURCE_STATUS.md)，显式App来源、原始位/255保留，不触发请求或自动控制；本机布局与通知仍未验收。


0.7.22新增[程序状态被动候选](../docs/APP_PROGRAM_STATUS.md)：显式App来源下38/64/6B独立帧快照，未知/重复记录保留，无查询/订阅/自动ACK，不等于物理完成；完整命令仍未验收。


0.7.23新增[单次程序状态请求](../docs/APP_PROGRAM_REQUEST.md)：显式App来源、固定type2与三个命名程序，仅关联ACK、业务体不透明；不承诺新通知，不增加连续订阅或动作执行，本机未验收。


0.7.24新增[程序状态推送启停请求](../docs/APP_PROGRAM_SUBSCRIPTION.md)：显式program与布尔enabled，固定type0/1及关联ACK；不证明远端订阅状态、不自动维护或恢复订阅，不发送动作程序命令。本机仍未验收。


0.7.25新增[外设状态源候选](../docs/APP_PERIPHERAL_STATUS.md)：46源类型/43 getter视图、保留tag21碰撞和GPS整数截断；不改现有姿态/关节，不自动ACK/订阅或控制，本机未验收。


## 0.7.26单次命名参数订阅 / 原生0.3.26 build29

显式App来源下发送固定DB已加载/HG724静态分支的152命名键非空单次04:12请求，CENTER/id7、无ACK；报告21元数据和2型号条件键。不提供空集停止、后台刷新、反向请求或重连重放；三条中位前导及独占操作槽，不由发送成功判断远端订阅、通知新鲜度或物理效果。详见[单次参数订阅](../docs/APP_PARAMETER_SUBSCRIPTION.md)。此版本扩展此前“仅研究/工作树开发”的历史状态；实际型号/路由/通知/远端停止仍待验收，全命令及高级门槛false，无硬件/实时UI/厂商执行。


## 0.7.27外设数据被动候选 / 原生0.3.27 build30

显式App来源下externalDeviceStatus/kind=externalDevice解析04:69完整TLV，tag2保留来源及三轴signed16原值、未知/重复与尾字节；Other7与未知原值分开，不继承源单例旧值或短包清零副作用。来源/断线清空，观察者隔离；不发送/订阅/自动ACK，不完成查询或改变姿态/关节、运动所有权。见[外设数据候选SDK](../docs/APP_EXTERNAL_DEVICE_STATUS.md)。本机布局/单位/参考系均未验收，未新增相机/视觉/高级功能，无硬件/liveUI/厂商执行，全命令门槛false；此前“仅研究未接SDK”为历史状态。


## 0.7.28传感器校准被动候选 / 原生0.3.28 build31

显式App来源下sensorCalibrationStatus/kind=sensorCalibration解析04:30两字节源进度/状态及尾部，保留0..255原值，映射0/1/3/9并标记未知；不复用08状态或旧inProgress，不补短包默认，不由COMPLETE结束查询/运动。缓存复制/不可变、观察者隔离、来源/断线清空。见[传感器校准候选SDK](../docs/APP_SENSOR_CALIBRATION_STATUS.md)。没有查询/订阅/自动ACK/校准触发或相机/视觉/高级新增；本机/单位/请求关联与物理完成未验收，无硬件/liveUI/厂商执行，全命令门槛false。此前当前App30“未接SDK”限定为历史状态。


## 0.7.29接收业务解析边界 / 原生0.3.29 build32

关联App ACK、04:05反馈、04:6E调参通知和旧研究状态拒绝加密/无效flags，原始帧保持可观察；加密读取不推进参数写入，加密关节不进入定位反馈。没有新增命令、解密、协商、硬件操作或高级功能，完整命令与高级门槛仍false。契约见 docs/PLAINTEXT_BOUNDARIES.md（仓库根目录）；本版本取代此前宽松解析行为，历史版本记录保留。


## 0.7.30部件校准候选 / 原生0.3.30 build33

显式App来源新增sendComponentCalibrationRequest(sourcePart=AUTO)，同一操作槽内停主机运动、读取35反向bit0门槛、发送04:08/00并等待严格关联ACK；禁用不自动开电机，读取与ACK共用截止时间，不重发/重放。返回码、可不完整的业务part/status和物理完成分开，不更新其他校准/传感器/姿态缓存，不提供固件中止或高级等待组合。见 docs/APP_COMPONENT_CALIBRATION.md（仓库根目录）。实际会话/设备/物理效果待验收，完整命令门槛false；未操作硬件或实时UI。


## 0.7.31手柄摇杆开关候选 / 原生0.3.31 build34

显式App来源新增sendHandheldStickControlRequest(enabled:boolean)，停止前验证/快照，同一操作槽内中位停止后一次04:58 bool00/01并等待严格关联ACK。不透明尾部保留，requestedEnabled不回写57缓存；无订阅/查询/重试/重放/反向回滚、摇杆接管或麦克风/相机/高级新增。见 docs/APP_HANDHELD_STICK_CONTROL.md（仓库根目录）。型号源链不等于实机效果或持久化，设备/物理/回读/通知关联标志false；未操作硬件/实时UI，完整命令门槛false。


## 0.7.32教程状态被动候选 / 原生0.3.32 build35

显式App来源下tutorialStatus（Python另有tutorial_status，原生appTutorialStatus）与kind=tutorial被动解码04:2B；保留步骤原值、完整32位无符号/有符号状态、9个数值标志、未知位与尾部，以及独立Java位移视图。未知步骤的源回退STEP_FINISH不是完成证明，bit30/31不解释为物理生命周期。缓存复制/不可变、观察者隔离，来源切换/断线清空；不发查询、订阅、ACK或04:2C，不结束查询或moveTo。本机布局/通知、请求关联及物理完成均未验收，完整命令和高级门槛仍false。契约见 docs/APP_TUTORIAL_STATUS.md（仓库根目录）。


## 0.7.33 CENTER只读信息候选 / 原生0.3.33 build36

显式App来源新增getCenterActivationInfo（Python另有get_center_activation_info，原生RSGimbal继承同名selector），要求sourceVersion四种已知格式，无默认/OTHER/协商。固定E5/CENTER-id7、COMMON00:32 GET01/11与严格关联明文ACK；完整本次业务体解析active/date/SN原始值及源signed-decimal字符串、尾部，无旧SN缓存成功回退。GIMBAL04:32同命令号隔离，原生完成后恢复普通04路由；无激活/绑定/SET/FAIL/自动回复/重试/重放或高级新增。见[接口契约](../docs/APP_CENTER_INFO.md)（仓库根目录）。设备/当前版本/布局/激活有效性未验收，全命令及高级门槛false，无硬件/liveUI/厂商执行。
