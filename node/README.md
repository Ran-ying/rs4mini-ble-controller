# RS4 Mini Node.js SDK 0.7.0

通过 Noble 直接连接 DJI RS 4 Mini，支持三轴速度、约 1 Hz 的姿态与关节反馈，以及低速关节位置闭环。完整参数、错误码和并发规则见 [API.md](API.md)。

0.7.0 增加自动重连、速度关键帧、逐点定位/停留、保存位置返回、显式四元数数学转换和独立实验协议配置。
自动重连不恢复运动；实验协议未在本机验证。范围见 [能力边界](../docs/CAPABILITIES.md)。
`node examples/expansion-demo.js --help` 只打印帮助，不初始化蓝牙；示例的运动和查询必须现场显式运行。

## 安装

```sh
npm ci
npm test
npm pack --dry-run
```

`npm test` 只用假适配器，不连接硬件。包内包含协议、遥测及生命周期测试。

## 只读连接

```js
import { RS4Mini } from './src/index.js';
const gimbal = new RS4Mini({ deviceId: null, rateHz: 15, ioTimeoutMs: 3000 });
try {
  console.log(await gimbal.connect({ timeoutMs: 30000 }));
  console.log(await gimbal.getAttitude({ fresh: true }));
  console.log(await gimbal.getJointAngles({ fresh: true }));
} finally {
  await gimbal.close();
}
```

安装到其他工程后可从 `rs4mini-sdk` 导入相同 API。每个进程必须重新连接；系统已连接不能代替当前进程的 GATT 句柄。仅缓存 `deviceId`，不缓存句柄。

## 运动

确认稳定器开机、负载平衡且无遮挡后执行。以下代码会移动硬件：

```js
const start = await gimbal.getJointAngles({ fresh: true });
const target = ((start.yaw + 3 + 540) % 360) - 180;
await gimbal.moveTo({ pan: target, toleranceDeg: 1 });
await gimbal.moveTo({ pan: start.yaw });
await gimbal.moveFor({ tilt: 0.05, durationMs: 300 });
```

`setVelocity({pan,tilt,roll})` 为归一化虚拟摇杆输入；缺省轴归零。`setVelocityDeg()` 用 Pan 37.5、Tilt 27.5、Roll 30 度/秒的经验满量程换算，受摇杆设置影响。

`moveTo()` 使用机械关节角：Pan ↔ Yaw，Tilt ↔ Pitch，Roll ↔ Roll。默认容差 1°、总超时 30 秒、单帧超时 3 秒、gain 0.02、minSpeed 0.05、maxSpeed 0.18。已进入容差的轴单独归零。位置环使用已验证的速度协议，不使用未验证的绝对角指令。

## 取消和并发

所有有限运动及其最后停止帧都保有操作所有权；冲突操作以 `RS4MINI_BUSY` 拒绝。手动连续速度可在前一次 `setVelocity()` 返回后更新。新的位置或限时操作会先停止旧连续速度。

```js
const movement = gimbal.moveTo({ pan: target });
const settled = movement.catch(error => {
  if (error.code !== 'RS4MINI_MOVE_CANCELLED') throw error;
});
await gimbal.stop();
await settled;
```

先给运动 promise 安装错误处理，再发起停止，避免应用自己的未处理拒绝。`stop()` 主动唤醒等待和限时睡眠，等待旧运动清理结束；之后的新运动不会被旧操作停止。完成、失败和取消均发送中位停止帧。GATT 帧的 20 字节切片不交错；若某次写入超时或失败，则清理并断开，不再拼接下一帧。

`disconnect()` 可以复用实例，`close()` 永久关闭实例并释放 Noble 运行循环。终止 CLI 时应捕获信号并在 `finally` 使用 `close()`。

## 回调与状态

`onNotification` 是原始块，`onMessage` 是 CRC 校验后的完整 DUML 帧，`onTelemetry` 是解析反馈。回调支持同步或异步函数，异常交给 `onError`；`onError` 自己的异常被隔离。回调和状态读取使用副本，修改副本不改变控制器缓存。

```js
gimbal.onTelemetry = sample => console.log(sample.jointAngles);
gimbal.onError = error => console.error(error);
```

`latestTelemetry` 和 `velocity` 为快照；`activeOperation`、`moveToActive` 用于显示运行状态。姿态角与机械关节角不同，不可互换。反馈内四个浮点值保留为 `orientationQuaternion.components`，坐标约定未验证。

## 硬件示例

- `npm run telemetry:capture`：5/10 秒反馈采样（`RS4MINI_CAPTURE_MS` 配置）。
- `npm run test:neutral`：连接并发送中位停止帧。
- `npm run example:position`：默认 Pan 5° 往返；`RS4MINI_POSITION_AXIS=pan|tilt|roll` 和 `RS4MINI_POSITION_DELTA` 配置轴/幅度。
- `npm run example:full`：包含三轴运动和回中，必须有人在场。
- `npm run telemetry:analyze -- captures/file.log`：离线回放原生抓包。

原始采样和设备缓存由 Git 忽略。0.6.0 修改的硬件验证统一记录在 [实机清单](../docs/HARDWARE_CHECKLIST.md)，当前不要将离线结果称为物理精度验证。
