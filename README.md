# rs4mini-ble-controller

通过 BLE 直接控制 DJI RS 4 Mini 的非官方开源项目。以 **Node.js 0.5.0** 为主版本，
提供三轴速度控制、姿态/关节反馈和低速关节位置闭环。主要实测平台为 macOS。

本项目当前只负责稳定器。相机取景、相机对焦/拍摄、目标识别和视觉跟踪均不属于当前实现。
仓库名为 `rs4mini-ble-controller`，现有 Node/Python 包名仍为 `rs4mini-sdk`。

## 快速开始

需要 Node.js 18+，首次安装需联网下载依赖。离线测试不会连接稳定器：

```sh
git clone https://github.com/Ran-ying/rs4mini-ble-controller.git
cd rs4mini-ble-controller/node
npm ci
npm test
```

稳定器开机、负载平衡并留出运动空间后，可以单独运行硬件测试：

```sh
npm run test:neutral
npm run example:position
```

默认位置演示是 Pan 5° 往返。选择其他轴或幅度：

```sh
RS4MINI_POSITION_DELTA=20 npm run example:position
RS4MINI_POSITION_AXIS=tilt RS4MINI_POSITION_DELTA=12 npm run example:position
RS4MINI_POSITION_AXIS=roll RS4MINI_POSITION_DELTA=12 npm run example:position
```

`npm run example:full` 演示连接、反馈读取、位置往返、三轴速度、停止和回中。
完整示例会保存本机 UUID，下次运行优先直接连接；缓存文件不会进入 Git。

## Node 调用示例

在 `node/` 下创建 `demo.mjs`：

```js
import { RS4Mini } from "./src/index.js";

const gimbal = new RS4Mini();
try {
  console.log("connected:", await gimbal.connect({ timeoutMs: 30_000 }));
  const start = await gimbal.getJointAngles({ fresh: true });
  const target = ((start.yaw + 5 + 540) % 360) - 180;
  console.log(await gimbal.moveTo({ pan: target, toleranceDeg: 1 }));
  console.log(await gimbal.moveTo({ pan: start.yaw, toleranceDeg: 1 }));
} finally {
  await gimbal.close();
}
```

| 能力 | 方法 |
|---|---|
| 扫描、UUID 直连及扫描回退 | `connect()` |
| 持续标准化速度 / 近似角速度 | `setVelocity()` / `setVelocityDeg()` |
| 限时运动并停止 | `moveFor()` |
| 姿态 / 三个机械关节角 | `getAttitude()` / `getJointAngles()` |
| 指定机械关节目标角度 | `moveTo()` |
| 停止并请求取消位置循环 | `stop()` |
| DJI 三轴回中 | `recenter()` |
| 断开 / 程序结束清理 | `disconnect()` / `close()` |

读取方法默认返回缓存；`fresh:true` 等待下一帧。`moveTo()` 中 Pan/Tilt/Roll 分别对应
关节 Yaw/Pitch/Roll，以度为单位。位置控制使用反馈加速度帧，反馈约 1 Hz，适合低速定位。
近似角速度受稳定器摇杆设置和负载影响。

每个新进程必须重新 `connect()`；系统显示已连接不能替代句柄初始化。
`close()` 后实例不可复用；需要同一进程再次连接时使用 `disconnect()`。

## 实现与验证状态

| 实现 | 状态 |
|---|---|
| `node/` | 主版本 0.5.0，Noble 后端，完整文档、离线测试与 TypeScript 声明 |
| `python/` | 早期 0.2.1，Bleak 异步控制；尚未同步遥测、位置闭环及新生命周期功能 |
| `macos/` | Objective-C / AppKit 原生控制面板；基础三轴速度、停止和回中 |
| `web/` | Web Bluetooth 模块和控制页；早期基础控制接口 |
| `tools/ble-probe/` | Objective-C 诊断探针，保留原始 BLE 研究能力 |

历史实机完成 Pan 20°、Tilt 12°、Roll 12° 单轴往返，返回端最后反馈误差分别为
0.36°、0.40°、0.90°。这些是单次安装下进入容差时的读数，不代表多轴轨迹或全部负载的精度保证。
Node 0.5.0 的并发/取消补丁有离线测试覆盖，尚无独立的补丁后硬件验证记录。

仍待处理的边界包括位置循环退出竞态、多轴逐轴容差、超时错误归一化、
完整连接截止时间、断线监听清理和一般运动操作调度。详见 [AGENTS.md](AGENTS.md)。

## 其他实现

Python：

```sh
cd python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m unittest discover -s tests -v
```

macOS 面板：

```sh
sh macos/build.sh
open "macos/RS 4 Mini Control.app"
```

浏览器页面：

```sh
python3 -m http.server 8000 --directory web
```

在支持 Web Bluetooth 的浏览器打开 localhost，并点击连接触发设备选择。
浏览器、OS 和蓝牙权限决定可用性；不能因为页面在手机上能打开就推断可以连接 BLE。
手机端不是当前主测试平台。

## 文档入口

- [Node 使用说明](node/README.md)：安装、所有方法、参数、回调和完整示例。
- [Node API 速查](node/API.md)：返回值、错误码和并发约定。
- [开发交接 AGENTS.md](AGENTS.md)：无需原对话即可了解范围、代码、测试和待解决问题。
- [协议记录](docs/PROTOCOL.md)：DUML、GATT、速度帧和遥测字节映射。
- [开发背景](docs/DEVELOPMENT.md)：研究路径、设计选择和各端差异。
- [验证记录](docs/VALIDATION.md)：历史实机数值和测试边界。
- [Node 版本记录](node/CHANGELOG.md)。
- [macOS 面板](macos/README.md)与[原生诊断探针](tools/ble-probe/README.md)。

## 仓库约定

不提交设备 UUID、原始抓包、依赖目录、编译缓存或生成的应用。第三方研究仓库没有打包进入本仓库。
Node 包使用原有锁文件，仓库上传不代表已发布 npm 包或可下载二进制版本。

许可证：[MIT](LICENSE)。本项目与 DJI 无官方隶属关系。
