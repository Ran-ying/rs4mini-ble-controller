# RS4 Mini Node API

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

- `query({kind:'version'|'position'|'controlStatus'|'type',timeoutMs:3000})` 发送限定查询，
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
