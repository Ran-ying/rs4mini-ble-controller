# RS4 Mini Node.js SDK

当前 Node.js 主版本：`0.5.0`。

这是一个通过 BLE 直接控制 DJI RS 4 Mini 的非官方 Node.js SDK。所有控制方法都是异步方法，需要使用 `await`。

本包只负责稳定器，不控制相机。Z6III 的 USB-C 可独立用于 UVC 取景，但相机进入 USB
串流模式后会限制其他输出和控制，因此相机对焦、拍照和录像不属于本 SDK 的当前范围。

已在 RS 4 Mini 实机验证：缓存 UUID 重连、三轴速度控制、停止、三轴回中、姿态反馈、
三轴关节反馈，以及 Pan 20°、Tilt 12°、Roll 12° 的单轴位置闭环。

- [完整 API 速查](./API.md)
- [版本记录](./CHANGELOG.md)
- 包内附带 TypeScript 类型声明，无需改写现有 JavaScript 调用代码。

## 安装与测试

```bash
cd rs4mini-ble-controller/node
npm install
npm test
```

运行完整实机演示：

```bash
npm run example:full
```

运行前请退出 DJI Ronin App 和其他正在连接稳定器的程序，并确保云台周围没有障碍物。

最小安全示例：

```js
import { RS4Mini } from "rs4mini-sdk";

const gimbal = new RS4Mini({ deviceId: process.env.RS4MINI_DEVICE_ID || null });

try {
  console.log("connected:", await gimbal.connect());
  console.log("joints:", await gimbal.getJointAngles({ fresh: true }));
  await gimbal.moveFor({ pan: 0.2, durationMs: 500 });
} finally {
  await gimbal.close();
}
```

## 创建控制器

```js
import { RS4Mini } from "./src/index.js";

const gimbal = new RS4Mini({
  nameIncludes: "DJI RS4 MINI",
  rateHz: 15,
  deviceId: null,
});
```

构造参数：

| 参数 | 默认值 | 功能 |
|---|---:|---|
| `nameIncludes` | `"DJI RS4 MINI"` | 扫描时匹配设备名称 |
| `rateHz` | `15` | 运动指令每秒发送次数，不是电机速度 |
| `deviceId` | `null` | 上次连接得到的 macOS CoreBluetooth UUID，可用于快速重连 |
| `adapter` | Noble | 测试或替换蓝牙后端，正常使用不用设置 |

## `connect()`：连接稳定器

```js
const name = await gimbal.connect({
  timeoutMs: 30_000,
  directConnectTimeoutMs: 5_000,
});

console.log(name);
console.log(gimbal.deviceId);
```

参数：

- `timeoutMs`：整个连接过程的超时，默认 30 秒。
- `directConnectTimeoutMs`：使用缓存 UUID 直接连接时的超时，默认 5 秒。
- `deviceId`：可以临时覆盖构造函数中的 UUID。

连接顺序：

1. 如果有 `deviceId`，先按 UUID 直接连接。
2. 直接连接失败时，自动扫描名称包含 `DJI RS4 MINI` 的设备。
3. 发现 FFF4/FFF5 蓝牙特征。
4. 订阅 FFF4 通知。
5. 返回设备名称。

每次启动新的 Node 进程都必须调用一次 `connect()`。CoreBluetooth 连接对象和特征句柄不能跨进程继承，但使用缓存 UUID 时通常不需要等待稳定器重新广播。

完整演示会把 UUID 保存到：

```text
node/.rs4mini-device.json
```

如果换了稳定器或缓存已经失效，删除这个文件即可重新扫描。

## `setVelocity()`：持续三轴速度控制

```js
await gimbal.setVelocity({
  pan: 0.4,
  tilt: -0.2,
  roll: 0.1,
});
```

三个输入值范围都是 `-1.0～+1.0`：

| 参数 | 正值方向 | 负值方向 |
|---|---|---|
| `pan` | 向右 | 向左 |
| `tilt` | 向上 | 向下 |
| `roll` | DJI 横滚正方向 | DJI 横滚反方向 |

超过范围会被自动限制。例如 `pan: 5` 会按照 `pan: 1` 发送。
参数名必须是 `pan`、`tilt`、`roll`；例如把 `tilt` 误写成 `tile` 会直接抛出错误，
不会再被静默忽略。

这个方法会以 `rateHz` 指定的频率持续发送运动帧，直到：

- 再次调用 `setVelocity()` 改变速度；
- 调用 `stop()`；
- 调用 `disconnect()` 或 `close()`；
- 蓝牙连接断开。

只控制一个轴：

```js
await gimbal.setVelocity({ pan: 0.35 });
```

动态改变方向：

```js
await gimbal.setVelocity({ pan: 0.4 });
await sleep(1000);

await gimbal.setVelocity({ pan: -0.4 });
await sleep(1000);

await gimbal.stop();
```

## `setVelocityDeg()`：近似角速度控制

```js
await gimbal.setVelocityDeg({
  pan: 12,
  tilt: -7,
  roll: 4,
});
```

目前这是经验换算，不是基于姿态反馈的精确速度闭环。默认满量程换算值：

```js
await gimbal.setVelocityDeg({
  pan: 12,
  tilt: 7,
  roll: 4,
  panFullScale: 37.5,
  tiltFullScale: 27.5,
  rollFullScale: 30,
});
```

相当于：

```js
await gimbal.setVelocity({
  pan: 12 / 37.5,
  tilt: 7 / 27.5,
  roll: 4 / 30,
});
```

实际速度仍会受到云台摇杆速度设置、电机参数、负载和平衡情况影响。

## `moveFor()`：限时运动并自动停止

这是普通自动化程序最推荐使用的方法。

```js
await gimbal.moveFor({
  pan: 0.4,
  tilt: 0.1,
  roll: 0,
  durationMs: 800,
});
```

它会开始持续运动，等待 `durationMs`，然后自动调用 `stop()`。即使等待过程中发生异常，也会尝试停止。

单轴运动：

```js
await gimbal.moveFor({
  pan: 0.45,
  durationMs: 900,
});
```

往返运动：

```js
await gimbal.moveFor({ pan: 0.4, durationMs: 800 });
await gimbal.moveFor({ pan: -0.4, durationMs: 800 });
```

## `getAttitude()`：读取机身姿态

```js
const attitude = await gimbal.getAttitude();
console.log(attitude.pitch, attitude.roll, attitude.yaw);
```

默认优先立即返回最近缓存的数据；尚未收到数据时会等待。要明确等待稳定器推送的下一帧：

```js
const attitude = await gimbal.getAttitude({
  fresh: true,
  timeoutMs: 3000,
});
```

返回值包含 `pitch`、`roll`、`yaw`、`unit`、`wrap`、`raw` 和 `timestamp`。
这里的姿态角描述相机/云台相对于参考坐标系的方向，不等于三个机械关节各自转了多少度。

## `getJointAngles()`：读取三轴关节角

```js
const joints = await gimbal.getJointAngles({ fresh: true });
console.log({
  pan: joints.yaw,
  tilt: joints.pitch,
  roll: joints.roll,
});
```

选项与 `getAttitude()` 相同。返回字段沿用协议名称 `pitch/roll/yaw`；映射到控制轴时，
`yaw = pan`、`pitch = tilt`、`roll = roll`。

## `moveTo()`：闭环移动到关节角

```js
const result = await gimbal.moveTo({
  pan: 20,       // 目标 Joint Yaw
  tilt: 5,       // 目标 Joint Pitch
  roll: -3,      // 目标 Joint Roll
  toleranceDeg: 1,
  timeoutMs: 30_000,
});

console.log(result.current, result.error);
```

只写一个轴即可只移动该轴，其余两轴发送零速度：

```js
const current = await gimbal.getJointAngles({ fresh: true });
const target = ((current.yaw + 5 + 540) % 360) - 180;
await gimbal.moveTo({ pan: target });
```

`moveTo()` 使用已经实测的速度指令和关节反馈做比例闭环，没有直接发送尚未在 RS 4 Mini
上验证的 DUML 绝对角命令。它会自动处理 Tilt 指令与 Joint Pitch 的方向差异；成功、超时、
断线或其他异常后都会调用 `stop()`。

RS 4 Mini 实机验证结果：Pan 20° 往返、Tilt 12° 往返和 Roll 12° 往返均正常完成，
各次最终关节误差均不超过默认的 `1°` 容差。

可调参数：

| 参数 | 默认值 | 功能 |
|---|---:|---|
| `toleranceDeg` | `1` | 三个已指定目标都进入该误差范围时完成 |
| `timeoutMs` | `30000` | 整个移动的最大时间 |
| `telemetryTimeoutMs` | `3000` | 等待单帧反馈的最大时间 |
| `gain` | `0.02` | 每度误差对应的标准化控制量 |
| `minSpeed` | `0.05` | 超出容差时克服死区的最小控制量 |
| `maxSpeed` | `0.18` | 闭环允许的最大控制量 |

目标值范围为 `-180°…+180°`。Pan 会走 ±180° 范围内的最短方向。RS 4 Mini 当前约每秒
推送一次 `04:05` 反馈，因此这是适合自动取景的低速位置控制，不是高频轨迹控制。

`moveTo()` 运行期间，另一个 `moveTo()`、`setVelocity()`、`moveFor()` 或 `recenter()` 会被
明确拒绝，避免两个控制循环互相覆盖。调用 `stop()` 会立即停止并取消闭环；进行中的
`moveTo()` 会在循环恢复时抛出 `code === "RS4MINI_MOVE_CANCELLED"`。主循环显式检测的位置
超时错误码为 `RS4MINI_MOVE_TIMEOUT`；若截止时间在等待遥测时到达，目前可能抛出普通遥测超时。

历史硬件验证覆盖单轴定位。多轴逐轴容差、停止阶段竞态和一般运动调度仍有待完善；
详见仓库根目录的 [AGENTS.md](../AGENTS.md) 与 [验证记录](../docs/VALIDATION.md)。

安全的小幅位置演示会读取当前 Pan、右移约 5°、再回到起点：

```bash
npm run example:position
```

可以用环境变量选择轴并调整往返幅度（默认 `pan` 和 `5°`，幅度限制在 `-90°…+90°`）：

```bash
RS4MINI_POSITION_DELTA=20 npm run example:position
RS4MINI_POSITION_AXIS=tilt RS4MINI_POSITION_DELTA=12 npm run example:position
RS4MINI_POSITION_AXIS=roll RS4MINI_POSITION_DELTA=12 npm run example:position
```

## `stop()`：停止三轴运动

```js
await gimbal.stop();
```

它会：

- 停止连续发送任务；
- 将 Pan、Tilt、Roll 全部设置为零；
- 连续发送三个全轴中位帧，降低残留运动风险。

调用全零速度也会进入相同的停止流程：

```js
await gimbal.setVelocity({ pan: 0, tilt: 0, roll: 0 });
```

## `recenter()`：三轴回中

```js
await gimbal.recenter();
```

它会先停止当前运动，然后发送 DJI 三轴回中指令。目前不能指定只回中 Pan、Tilt 或 Roll。

## `disconnect()`：断开但保留蓝牙运行环境

```js
await gimbal.disconnect();
```

它会停止运动、发送三个停止帧、取消 FFF4 通知订阅并断开当前稳定器，但保留 Noble 蓝牙运行环境。

适合在同一个 Node 进程里稍后重新连接：

```js
await gimbal.connect();
await gimbal.moveFor({ pan: 0.3, durationMs: 500 });

await gimbal.disconnect();

// 同一个进程稍后重新连接；deviceId 会继续保留。
await gimbal.connect();
```

## `close()`：程序最终退出

```js
await gimbal.close();
```

它会安全停止、断开稳定器、停止扫描，并关闭 Noble 的原生 CoreBluetooth 运行循环。独立命令行程序的 `finally` 应使用 `close()`：

```js
try {
  await gimbal.connect();
  await gimbal.moveFor({ pan: 0.4, durationMs: 800 });
} finally {
  await gimbal.close();
}
```

调用 `close()` 后，这个实例不能再次连接，需要创建新的实例：

```js
const savedDeviceId = gimbal.deviceId;
await gimbal.close();

const next = new RS4Mini({ deviceId: savedDeviceId });
await next.connect();
```

## 状态属性

| 属性 | 内容 |
|---|---|
| `connected` | 当前是否已经连接 |
| `deviceName` | 当前连接设备的名称 |
| `deviceId` | macOS CoreBluetooth UUID |
| `velocity` | 当前设置的 `{ pan, tilt, roll }` |
| `rateHz` | 指令发送频率 |
| `nameIncludes` | 扫描名称关键字 |
| `latestTelemetry` | 最近一个已解码的姿态/关节反馈；尚未收到时为 `null` |

```js
if (gimbal.connected) {
  console.log("已连接:", gimbal.deviceName);
  console.log("设备 UUID:", gimbal.deviceId);
  console.log("当前速度:", gimbal.velocity);
}
```

## 回调

### `onNotification`：原始 FFF4 通知块

```js
gimbal.onNotification = packet => {
  console.log(packet.toString("hex"));
};
```

这里收到的是单次 BLE 通知块，不保证恰好等于一个完整 DUML 帧。

### `onMessage`：完整 DUML 消息

SDK 会处理 BLE 分片、多个帧粘连、CRC8/CRC16 校验和错误数据重同步，再把每个完整帧交给回调：

```js
gimbal.onMessage = message => {
  console.log({
    commandSet: message.commandSet,
    commandId: message.commandId,
    sequence: message.sequence,
    payloadHex: message.payload.toString("hex"),
  });
};
```

### `onTelemetry`：姿态与三轴关节反馈

```js
gimbal.onTelemetry = sample => {
  console.log("attitude:", sample.attitude);
  console.log("joint angles:", sample.jointAngles);
};
```

RS 4 Mini 会约每秒推送一次 `cmdSet=0x04, cmdId=0x05`。下列映射已经通过静止、
Pan、Tilt、Roll 三组往返运动和手柄转动样本验证：

| 数据 | Payload 偏移 | 编码 | 返回单位 |
|---|---:|---|---|
| 姿态 Pitch/Roll/Yaw | `0/2/4` | 三个 `int16 LE × 0.1°` | 度，±180° 环绕 |
| 关节 Pitch | `20` | `int16 LE × 0.1°` | 度 |
| 关节 Roll | `22` | `int16 LE × 0.1°` | 度 |
| 关节 Yaw | `16` | `int16 LE × 0.01°` | 度 |

完整对象示意：

```js
{
  kind: "gimbal-telemetry",
  verified: true,
  attitude: {
    pitch: -172.5,
    roll: 0.6,
    yaw: 80.6,
    unit: "deg",
    wrap: 180,
    raw: { pitch: -1725, roll: 6, yaw: 806 }
  },
  jointAngles: {
    pitch: 4.1,
    roll: 1.1,
    yaw: 81.88,
    unit: "deg",
    raw: { pitch: 41, roll: 11, yaw: 8188 }
  }
}
```

顶层的 `pitch/roll/yaw` 保留为 `attitude` 的兼容别名。载荷 `24–39` 还能读出
4 个归一化浮点数；它们很可能是四元数，但 DJI 未公开 RS 4 Mini 的分量顺序和坐标系，
因此 SDK 只以 `orientationQuaternion.components` 暴露，并将 `componentOrder` 标记为
`"unverified"`，不会擅自换算欧拉角。

只读抓取 10 秒 FFF4 数据：

```bash
npm run telemetry:capture
```

自定义抓取时长：

```bash
RS4MINI_CAPTURE_MS=20000 npm run telemetry:capture
```

抓取结果保存在 `node/captures/*.jsonl`，其中记录完整 DUML 帧、命令号、payload 和原始帧。
该目录已被 `.gitignore` 排除，以免设备数据被打包或提交。

如果原始通知由 macOS CoreBluetooth 探针记录，可以用同一 Node 解码器离线重放：

```bash
npm run telemetry:analyze -- captures/native-static.log
```

### `onDisconnect`：连接断开

```js
gimbal.onDisconnect = reason => {
  console.log("稳定器断开:", reason);
};
```

### `onError`：连续发送错误

```js
gimbal.onError = error => {
  console.error("运动指令发送失败:", error);
};
```

建议在连接前设置回调。

## 完整调用示例

```js
import { RS4Mini } from "./src/index.js";

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

const gimbal = new RS4Mini({
  nameIncludes: "DJI RS4 MINI",
  rateHz: 15,
  deviceId: null, // 可以换成上次保存的 UUID
});

gimbal.onNotification = packet => {
  if (process.env.RS4MINI_LOG_PACKETS === "1") {
    console.log("notify:", packet.toString("hex"));
  }
};

gimbal.onDisconnect = reason => {
  console.log("disconnected:", reason);
};

gimbal.onError = error => {
  console.error("BLE error:", error);
};

try {
  const name = await gimbal.connect({ timeoutMs: 30_000 });

  console.log("connected:", name);
  console.log("deviceId:", gimbal.deviceId);

  await gimbal.moveFor({
    pan: 0.4,
    durationMs: 800,
  });

  await sleep(300);

  await gimbal.moveFor({
    tilt: 0.3,
    durationMs: 600,
  });

  await sleep(300);

  await gimbal.setVelocity({
    pan: -0.3,
    tilt: -0.2,
    roll: 0.1,
  });

  await sleep(700);
  await gimbal.stop();

  await gimbal.setVelocityDeg({
    pan: 10,
    tilt: 5,
    roll: 2,
  });

  await sleep(700);
  await gimbal.stop();

  await gimbal.recenter();
  await sleep(2000);
} finally {
  await gimbal.close();
}
```

## 底层协议函数

SDK 还导出了以下底层函数：

```js
import {
  crc8,
  crc16,
  frame,
  velocityFrame,
  stopFrame,
  recenterFrame,
  parseDumlFrame,
  DumlStreamDecoder,
  decodeGimbalTelemetry,
} from "./src/index.js";
```

这些函数用于构造协议包、重组 FFF4 通知、解码遥测和执行协议测试。普通控制程序应优先使用
`RS4Mini` 类的 `onTelemetry` / `latestTelemetry`。

## 范围与限制

- 单轴回中；
- 意外断线后的自动重连；
- 目标识别和视觉跟踪。
- Z6III 或其他相机的对焦、拍照和录像控制；
- 高频轨迹规划；`moveTo()` 的反馈频率约为 1 Hz。

## 相关文件

- `src/index.js`：Node SDK 主实现；
- `src/index.d.ts`：完整公共 TypeScript 类型；
- `src/protocol.js`：DUML 封包与校验；
- `src/telemetry.js`：通知流重组、CRC 校验、姿态和三轴关节反馈解码；
- `API.md`：公共方法、参数、返回值、错误码和并发规则速查；
- `CHANGELOG.md`：版本变更记录；
- `examples/full-demo.js`：完整实机演示和设备 UUID 缓存；
- `examples/position-demo.js`：读取反馈、Pan 小幅闭环定位并返回起点；
- `examples/connection-test.js`：无需稳定器的连接流程测试；
- `examples/protocol-test.js`：协议黄金向量测试；
- `examples/telemetry-test.js`：无需稳定器的通知流、姿态与关节解码测试；
- `examples/telemetry-capture.js`：只读实机通知抓取工具；
- `examples/telemetry-analyze.js`：用 Node 解码器重放并统计原生 FFF4 抓取；
- `examples/neutral-test.js`：仅连接并发送停止帧；
- `examples/three-axis.js`：简单三轴运动示例。
