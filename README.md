# rs4mini-ble-controller

通过电脑 BLE 直接控制 **DJI RS 4 Mini** 的非官方 SDK。Node.js 为主实现，Python 提供异步接口，macOS 提供原生控制面板。

当前版本：Node / Python **0.7.39**；macOS **0.3.41 / build 44**。包名为 `rs4mini-sdk`，目前通过源码或本地打包安装，未发布到 npm / PyPI。

## 当前能力

- 三轴速度、限时运动、停止、三轴回中。
- 姿态角与机械关节角反馈；基于关节反馈的 `moveTo()` 定位。
- 跟随灵敏度、跟随 / RC 档位及数值、自定义跟随、电机设置、轴模式、配置与工作模式的读取和设置。
- 12 项电机参数逐项读取与单项设置。
- 电机自动调参、AUTO 水平校准、Pitch / Roll 手动微调，以及四类保留状态通知。
- 已有主机组合能力：速度轨迹、关节路点、保存位置返回、有界自动重连。

应用统一从 `RS4Mini` 进入：基础操作直接调用，命名设备参数从同一实例的 `appCommands` 调用，共用一条连接。`moveTo()`、轨迹和路点是电脑端组合算法，详见[架构边界](docs/ARCHITECTURE.md)。

当前保留范围及验收见[项目状态](docs/PROJECT_STATUS.md)、[Node 连续验收](docs/SDK_NODE_CONTINUOUS_ACCEPTANCE.md)和[接口清理说明](docs/SDK_UNVERIFIED_REMOVAL.md)。全部固件蓝牙命令尚未解析完成；相机控制、视觉跟踪与 Web 端不在当前范围。

## 部署准备

以下命令以 macOS 的 Terminal / zsh 为例，安装到主目录。当前实机验证平台为 macOS；Linux / Windows 的蓝牙后端及权限需要另行验证。

- Node.js **18+**；Python **3.8+**，新部署建议使用 Python 3.12。
- macOS 安装 Xcode Command Line Tools：尚未安装时执行 `xcode-select --install`，用于原生依赖和面板构建。
- 在“系统设置 → 隐私与安全性 → 蓝牙”允许运行脚本的 Terminal / IDE 使用蓝牙。
- 稳定器开机并启用蓝牙，退出 DJI App 或其他占用它的控制程序。读取反馈不需要先在系统蓝牙页面配对；脚本仍需执行 `connect()`。

```sh
git clone https://github.com/Ran-ying/rs4mini-ble-controller.git "$HOME/rs4mini-ble-controller"
cd "$HOME/rs4mini-ble-controller"
```

已有仓库时，在工作树干净的前提下执行 `git pull --ff-only`。下面 Node 和 Python 可任选一端部署。

## Node.js 部署与调用

### 安装

先安装仓库依赖并离线测试，再创建独立调用工程：

```sh
cd "$HOME/rs4mini-ble-controller"
npm --prefix node ci
npm --prefix node test

mkdir -p "$HOME/rs4mini-node-app"
cd "$HOME/rs4mini-node-app"
npm init -y
npm install "$HOME/rs4mini-ble-controller/node"
```

这是本地源码安装，不要用 `npm install rs4mini-sdk` 代替。示例使用 `.mjs`，无需修改应用的 `package.json`。

### 连接并读取

在 `~/rs4mini-node-app/` 保存为 `read.mjs`：

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

```sh
cd "$HOME/rs4mini-node-app"
node read.mjs
```

这个示例连接设备、读取反馈和参数后关闭，不发送运动或校准请求。电机的 12 项参数按单项顺序读取；多项结果为 `readMode: 'sequential'`、`atomic: false`，读取 `values` 和 `replies`，不是同一时刻的原子快照。

### 小幅运动

稳定器三轴解锁、负载平衡且周围无遮挡后，在同一目录保存为 `move.mjs`。这段会先 Pan 约 3° 往返，再以低速向 Tilt 方向运动 300 ms：

```js
import { RS4Mini } from 'rs4mini-sdk';

const gimbal = new RS4Mini();
try {
  await gimbal.connect();
  const start = await gimbal.getJointAngles({ fresh: true });
  const target = ((start.yaw + 3 + 540) % 360) - 180;
  await gimbal.moveTo({ pan: target, toleranceDeg: 1 });
  await gimbal.moveTo({ pan: start.yaw, toleranceDeg: 1 });
  await gimbal.moveFor({ tilt: 0.05, durationMs: 300 });
} finally {
  await gimbal.close();
}

```

```sh
node move.mjs
```

若需在连接期间持续观察反馈，可设置 `gimbal.onTelemetry = sample => console.log(sample.jointAngles)`；四类设备状态通过 `gimbal.onAppStatus` 接收，需先选择 App 来源配置。

## Python 部署与调用

### 安装

```sh
cd "$HOME/rs4mini-ble-controller"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ./python
.venv/bin/python -m unittest discover -s python/tests -v
```

依赖 Bleak 由 pip 安装。后续始终使用这个虚拟环境的 Python；不需要 `sudo pip` 或修改系统 Python。

### 连接并读取

在仓库根目录保存为 `read.py`：

```python
import asyncio
from rs4mini_sdk import RS4Mini

async def main():
    gimbal = RS4Mini(ioTimeoutMs=3000)
    gimbal.onError = lambda error: print(error.code, str(error))
    try:
        await gimbal.connect(timeoutMs=30000)
        print("姿态角：", await gimbal.getAttitude(fresh=True))
        print("机械关节角：", await gimbal.getJointAngles(fresh=True))

        gimbal.appCommands.useProfile("ronin-2.2.2")
        print("跟随灵敏度：", await gimbal.appCommands.getFollowSensitivity())
        print("电机参数：", await gimbal.appCommands.getMotorTuning(timeoutMs=15000))
    finally:
        await gimbal.close()

if __name__ == "__main__":
    asyncio.run(main())

```

```sh
cd "$HOME/rs4mini-ble-controller"
.venv/bin/python read.py
```

这个示例与 Node 读取相同类别的数据，不触发运动或校准。Python 通过 `asyncio` 顺序等待各次操作。

### 小幅运动

与 Node 示例相同的 Pan 约 3° 往返与低速 Tilt 300 ms，保存为仓库根目录的 `move.py`：

```python
import asyncio
from rs4mini_sdk import RS4Mini

async def main():
    gimbal = RS4Mini()
    try:
        await gimbal.connect()
        start = await gimbal.getJointAngles(fresh=True)
        target = (start["yaw"] + 3 + 180) % 360 - 180
        await gimbal.moveTo(pan=target, toleranceDeg=1)
        await gimbal.moveTo(pan=start["yaw"], toleranceDeg=1)
        await gimbal.moveFor(tilt=0.05, durationMs=300)
    finally:
        await gimbal.close()

if __name__ == "__main__":
    asyncio.run(main())

```

```sh
.venv/bin/python move.py
```

Python 同时提供 snake_case 别名，例如 `get_joint_angles(fresh=True, timeout_ms=3000)`、`move_to(pan=10, tolerance_deg=1)`。注意 `moveFor(durationMs=300, ...)` 使用毫秒，旧别名 `move_for(0.3, ...)` 使用秒。

## 常用调用对照

下列调用均在连接成功后执行，`gimbal` 为同一实例。参数接口先调用 `appCommands.useProfile('ronin-2.2.2')`，无需再创建第二个控制器。

| 操作 | Node.js | Python |
|---|---|---|
| 新鲜姿态反馈 | `await gimbal.getAttitude({fresh: true})` | `await gimbal.getAttitude(fresh=True)` |
| 新鲜关节反馈 | `await gimbal.getJointAngles({fresh: true})` | `await gimbal.getJointAngles(fresh=True)` |
| 连续低速 Pan | `await gimbal.setVelocity({pan: 0.05})` | `await gimbal.setVelocity(pan=0.05)` |
| 停止主机运动 | `await gimbal.stop()` | `await gimbal.stop()` |
| 三轴回中 | `await gimbal.recenter()` | `await gimbal.recenter()` |
| 读取跟随灵敏度 | `await gimbal.appCommands.getFollowSensitivity()` | `await gimbal.appCommands.getFollowSensitivity()` |
| 设置跟随灵敏度 | `await gimbal.appCommands.setFollowSensitivity({mode: 1})` | `await gimbal.appCommands.setFollowSensitivity(mode=1)` |
| 读取 Pitch 电机四项 | `await gimbal.appCommands.getMotorTuning({axis: 'pitch'})` | `await gimbal.appCommands.getMotorTuning(axis='pitch')` |
| 永久关闭并释放资源 | `await gimbal.close()` | `await gimbal.close()` |

`setVelocity()` 会持续发帧，直到更新速度、停止或关闭；需要有界时长时优先使用 `moveFor()`。设置参数会改变设备状态，按需要显式调用；部署读取示例不执行写入。自动调参和水平校准结束后可能需要在稳定器屏幕手动确认，调用格式见[调参与状态](docs/APP_CALIBRATION.md)、[水平校准](docs/APP_COMPONENT_CALIBRATION.md)和[微调](docs/APP_FINE_TUNE.md)。

## 反馈、运动与连接约定

- 姿态角描述平台姿态，机械关节角描述轴的位置，不能互换。`moveTo()` 的 `pan / tilt / roll` 分别对应关节 `yaw / pitch / roll`，单位为度。
- `fresh: true` 等待下一条反馈，不发送主动姿态查询；当前反馈约 1 Hz。默认定位容差 1°，适合低速定位；±180° 的输入范围不是机械安全范围。
- `stop()` 取消主机运动并发送三个中位帧；不保证中止固件校准任务。蓝牙丢失后，软件无法保证设备收到停止。
- 有限运动与参数写入共享操作槽。出现 `RS4MINI_BUSY` 时等待当前操作完成，避免并发启动运动或写入。
- `disconnect()` 后实例可重新连接；`close()` 永久关闭实例。脚本用 `try/finally` 调用 `close()`，确保释放 Noble / Bleak 连接。
- 自动重连默认关闭，需显式启用；重连只恢复链路，不恢复旧速度或轨迹。

## 常见问题

| 现象 | 检查方法 |
|---|---|
| 连接超时 / 搜不到 | 检查开机、蓝牙权限及其他 App 占用；不要同时运行 Node、Python 和原生面板连接同一设备 |
| 系统显示已连接，脚本仍未连接 | 每个进程都需要自己的 `connect()` 和 GATT 句柄；系统状态不能代替 SDK 连接 |
| 想复用设备 ID | Node：`new RS4Mini({deviceId: '本机缓存ID'})`；Python：`RS4Mini(deviceId='本机缓存ID')`。macOS 使用 CoreBluetooth UUID，设备标识不提交仓库 |
| 反馈超时 | 确认设备未断开；`getJointAngles` 等待约 1 Hz 推送，按需增大 `timeoutMs` |
| Node 脚本结束后仍不退出 | 检查是否在 `finally` 中 `await gimbal.close()` |
| Python 导入失败 | 检查运行脚本的解释器是否为安装 SDK 的 `.venv/bin/python` |
| 请求超时 | 不代表设备一定未执行，写入或维护请求不要盲目自动重试 |

## 开发检查与 macOS 面板

Node 的 `npm test` 和 Python 的单元测试使用假设备，不扫描、不连接、不移动硬件。完整开发检查还需要 Xcode 工具及已缓存的 TypeScript：

```sh
cd "$HOME/rs4mini-ble-controller"
(cd node && npm exec --yes --package typescript@5.9.3 -- tsc --version)
RS4MINI_PYTHON="$PWD/.venv/bin/python" sh tools/check-offline.sh
```

原生界面构建和启动：

```sh
sh macos/build.sh
open "macos/RS 4 Mini Control.app"
```

## 文档入口

- [Node 部署说明](node/README.md) · [完整 Node API](node/API.md) · [Python 部署说明](python/README.md)
- [macOS 面板](macos/README.md) · [GUI SDK 入口](docs/MACOS_SDK_PANEL.md)
- [SDK 独立复刻规范](docs/SDK_RECONSTRUCTION_SPEC.md)：全部现存蓝牙通道、命令、响应、参数布局、参考代码和合成报文
- [项目状态](docs/PROJECT_STATUS.md) · [底层命令清单](docs/SDK_COMMANDS.md) · [研究路线](docs/RESEARCH_ROADMAP.md)
- [Node 连续验收](docs/SDK_NODE_CONTINUOUS_ACCEPTANCE.md) · [维护功能验收](docs/SDK_ACCEPTANCE_QUEUE.md) · [移除接口记录](docs/SDK_UNVERIFIED_REMOVAL.md)
- [协议记录](docs/PROTOCOL.md) · [开发背景](docs/DEVELOPMENT.md) · [开发交接](AGENTS.md)

历史版本和研究证据保留在各专题文档及 Git 记录中；当前可调用接口以本版本 API 和复刻规范为准。源码以 MIT 许可提供，与 DJI 无官方隶属关系。
