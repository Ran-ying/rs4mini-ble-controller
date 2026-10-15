# RS4 Mini Node API

所有公共方法均为异步方法。除读取缓存状态外，请在调用前完成 `await gimbal.connect()`。

## `new RS4Mini(options?)`

```ts
type ControllerOptions = {
  nameIncludes?: string; // 默认 "DJI RS4 MINI"
  rateHz?: number;       // 默认 15，仅为命令发送频率
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

到时或发生异常都会尝试停止。

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

- `moveTo()` 运行期间，另一个 `moveTo()`、`setVelocity()`、`moveFor()` 或 `recenter()` 会被拒绝；
- 调用 `stop()` 会立即发送停止帧，并使进行中的 `moveTo()` 以
  `error.code === "RS4MINI_MOVE_CANCELLED"` 结束；
- 主循环显式检测到总超时时，使用 `error.code === "RS4MINI_MOVE_TIMEOUT"`，并附带
  `target` 和 `current`。若截止时间在等待遥测时到达，目前可能抛出普通遥测超时错误。

`stop()` 返回时，正在等待下一帧的 `moveTo()` promise 可能尚未结束；在开始另一项运动前
应等待该 promise 结束。多轴逐轴到位、退出清理竞态等边界见仓库根目录的 `AGENTS.md`。

### `stop()` 与 `recenter()`

`stop()` 停止命令流并连续发送三个全轴中位帧。`recenter()` 先停止，再执行 DJI 的三轴回中；
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
| `onNotification` | 原始 FFF4 BLE 通知块 |
| `onMessage` | CRC 校验后的完整 DUML 消息 |
| `onTelemetry` | 解码后的 `04:05` 反馈 |
| `onDisconnect` | 意外或主动断开通知 |
| `onError` | 后台运动流写入错误 |

完整 TypeScript 类型由 `src/index.d.ts` 随包提供。
