# Node.js SDK 0.7.39

通过 Noble 直接连接 DJI RS 4 Mini。Node.js 18+，当前实机平台为 macOS；原生依赖需要 Xcode Command Line Tools，运行宿主需要蓝牙权限。

## 在仓库中部署

以下命令从仓库根目录执行：

```sh
npm --prefix node ci
npm --prefix node test
```

测试使用假适配器，不连接硬件。在 `node/` 目录创建 `.mjs` 脚本时，从 `./src/index.js` 导入 `RS4Mini`。

## 在自己的程序中使用

SDK 未发布到 npm。先克隆仓库，再在调用工程中安装本地源码：

```sh
mkdir -p "$HOME/rs4mini-node-app"
cd "$HOME/rs4mini-node-app"
npm init -y
npm install "$HOME/rs4mini-ble-controller/node"
```

保存为 `read.mjs`，执行 `node read.mjs`：

```js
import { RS4Mini } from 'rs4mini-sdk';

const gimbal = new RS4Mini({ ioTimeoutMs: 3000 });
gimbal.onError = error => console.error(error.code, error.message);
try {
  await gimbal.connect({ timeoutMs: 30000 });
  console.log('姿态角：', await gimbal.getAttitude({ fresh: true }));
  console.log('机械关节角：', await gimbal.getJointAngles({ fresh: true }));

  gimbal.appCommands.useProfile('ronin-2.2.2');
  console.log('跟随灵敏度：', await gimbal.appCommands.getFollowSensitivity());
  console.log('电机参数：', await gimbal.appCommands.getMotorTuning({ timeoutMs: 15000 }));
} finally {
  await gimbal.close();
}

```

示例读取反馈和参数，不触发运动或校准。设备参数先显式选择 `ronin-2.2.2` 来源，通过同一对象的 `appCommands` 调用；不创建额外连接。

## 运动调用

稳定器解锁、平衡且周围无遮挡后使用。以下片段替换读取示例 `try` 内的读取部分：

```js
await gimbal.moveFor({ pan: 0.05, durationMs: 300 });
const start = await gimbal.getJointAngles({ fresh: true });
const target = ((start.yaw + 3 + 540) % 360) - 180;
await gimbal.moveTo({ pan: target, toleranceDeg: 1 });
await gimbal.moveTo({ pan: start.yaw, toleranceDeg: 1 });
```

`setVelocity({pan, tilt, roll})` 为持续发送的归一化输入 -1..1；用 `stop()` 结束。`moveTo()` 是主机反馈闭环，目标为机械关节角：Pan=Yaw、Tilt=Pitch、Roll=Roll，单位度。反馈约 1 Hz，默认容差 1°。`recenter()` 是设备三轴回中，不要求关节角归零。

所有有限运动与参数写入共享操作槽，冲突报 `RS4MINI_BUSY`。需要取消运动时，先给运动 promise 安装拒绝处理，再调用 `stop()`；完整示例见 [API](API.md)。`disconnect()` 允许重连，`close()` 永久关闭实例并释放 Noble，CLI 在 `finally` 中调用。

## 打包与安装

```sh
cd "$HOME/rs4mini-ble-controller/node"
npm pack
# 在调用工程内执行，将路径替换为上一步生成的文件：
# npm install /绝对路径/rs4mini-sdk-0.7.39.tgz
```

本地源码安装适合开发；需要固定分发内容时使用 tarball。

完整的部署、Python 对照、故障排查及现存能力见[主 README](../README.md)。接口参数与错误码见 [API.md](API.md)，历史变更见 [CHANGELOG.md](CHANGELOG.md)，报文复刻见[单文件规范](../docs/SDK_RECONSTRUCTION_SPEC.md)。当前范围不包含 Web、相机控制或视觉跟踪，也不宣称完整实现全部固件命令。
