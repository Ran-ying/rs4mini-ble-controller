# rs4mini-ble-controller

通过电脑 BLE 直接控制 DJI RS 4 Mini 的非官方项目。Node.js **0.7.8** 为主实现；Python/Web **0.7.8**、macOS 原生面板 **0.3.8** 提供三轴速度、姿态/机械关节反馈、低速定位、轨迹与路点、保存位置返回和显式自动重连。相机控制和视觉跟踪不属于当前范围。

**当前状态：底层 SDK 已增加当前 App 参数事务、调参请求与状态封装；全部非相机 BLE 能力仍未完成。**
完成项、验证证据与后续接手入口统一保存在 [项目状态](docs/PROJECT_STATUS.md)。

## 安装与离线验证

需要 Node.js 18+。macOS 原生构建还需要 Xcode Command Line Tools。

```sh
git clone https://github.com/Ran-ying/rs4mini-ble-controller.git
cd rs4mini-ble-controller
npm --prefix node ci
python3 -m venv python/.venv
python/.venv/bin/python -m pip install --upgrade pip
python/.venv/bin/python -m pip install -e ./python
cd node
npm exec --yes --package typescript@5.9.3 -- tsc --version
cd ..
sh tools/check-offline.sh
```

统一检查不扫描、不连接、不移动稳定器；TypeScript 首次缓存后使用离线模式。单独运行：

```sh
npm --prefix node test
npm --prefix web test
python/.venv/bin/python -m unittest discover -s python/tests -v
sh macos/test.sh
```

## Node 使用

在 `node/` 目录下创建脚本：

```js
import { RS4Mini } from './src/index.js';
const gimbal = new RS4Mini({ ioTimeoutMs: 3000 });
try {
  await gimbal.connect({ timeoutMs: 30000 });
  console.log(await gimbal.getJointAngles({ fresh: true }));
} finally {
  await gimbal.close();
}
```

运动前确认负载平衡、无遮挡，并退出其他控制程序。下列命令会连接硬件，位置演示会移动：

```sh
cd node
npm run telemetry:capture
npm run test:neutral
npm run example:position
RS4MINI_POSITION_AXIS=tilt RS4MINI_POSITION_DELTA=3 npm run example:position
```

默认位置示例为 Pan 5° 往返。`moveTo()` 以机械关节角为目标：Pan=Yaw、Tilt=Pitch、Roll=Roll；反馈约 1 Hz，适用于低速定位。`setVelocityDeg()` 是经验换算，不是闭环角速度。

## SDK 与组合能力

蓝牙设备 SDK 负责连接、协议、设备指令和反馈；`moveTo()`、轨迹、路点与保存位置返回由电脑端组合这些能力实现。
当前已拆为设备 SDK 与高级封装两个模块，应用仅使用 `RS4Mini`（原生为 `RSGimbal`）入口；基础操作也通过该入口访问。能力归属、姿态/关节解释及剩余功能可行性见 [架构边界](docs/ARCHITECTURE.md)。

## 各端状态

| 功能 | Node 0.7.6 | Python 0.7.6 | Web 0.7.6 | macOS 面板 0.3.6 |
|---|---|---|---|---|
| 三轴速度 / 停止 / 三轴回中 | 有 | 有 | 有 | 有 |
| 反馈解析与 CRC 重组 | 有 | 有 | 共享 Node 核心 | 有 |
| 关节目标位置 / 逐轴容差 | 可配置 | 可配置 | 可配置 + 页面输入 | 固定低速参数 + 面板输入 |
| 限时运动 / 角速度换算 | 有 | 有 | 有 | 手动按住控制 |
| 取消与停止阶段互斥 | 有 | 有 | 共享 Node 核心 | 有 |
| 连接截止时间与清理 | 有 | 有 | 含设备选择等待 | 有，30 秒 |
| 缓存 ID 重连 | 有 | 有 | 已授权设备在当前实例重用 | 检索系统连接与重新扫描 |
| 失焦停止 | 由调用方实现 | 由调用方实现 | 隐藏/失焦/离开页面 | 失焦/退出 |
| 有界自动重连，不恢复运动 | 显式启用 | 显式启用 | 当前已选设备 | 当前设备 ID，最多 5 次 |
| 插值速度轨迹 / 关节路点与停留 | 有 | 有 | SDK + JSON 页面入口 | API + JSON 文件载入 |
| 保存位置与选轴返回 | 有 | 有 | 有 | 有 |
| 显式顺序四元数数学转换 | 有 | 有 | 有 | 有 |
| 独立实验协议配置 | 有 | 有 | 有 | 有，查询独占操作槽 |

各端新代码均有离线验证；新运动行为尚待统一实机验证。历史 Node 单轴定位与 0.5.0 的连接采样证据见 [验证记录](docs/VALIDATION.md)，不能代替新版本的物理运动测试。

## 其他端启动

Python 只读反馈和小幅位置示例：

```sh
python/.venv/bin/python python/examples/telemetry_capture.py
python/.venv/bin/python python/examples/position_demo.py
```

原生面板：

```sh
sh macos/build.sh
open "macos/RS 4 Mini Control.app"
```

Web 必须从仓库根目录提供服务，页面会加载 `node/src/` 内不依赖 Noble 的共享模块：

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

打开 `http://127.0.0.1:8000/web/`。使用支持 Web Bluetooth 的浏览器并从点击操作选择设备。

**底层命令完整性尚未验收，暂不新增高级功能。** 已知命令、未知字段和本机证据分别列在 [设备命令审计](docs/SDK_COMMANDS.md)，机器清单为 `protocol/COMMANDS.json`。

## 文档和限制

- [Node 使用说明](node/README.md)、[完整 API](node/API.md)、[版本记录](node/CHANGELOG.md)
- [Python 说明](python/README.md)、[Web 说明](web/README.md)、[macOS 说明](macos/README.md)
- [协议](docs/PROTOCOL.md)、[开发交接](AGENTS.md)、[开发背景](docs/DEVELOPMENT.md)
- [统一实机清单](docs/HARDWARE_CHECKLIST.md)、[代码验收计划](docs/IMPLEMENTATION_PLAN.md)

停止通过 BLE 发送三个中位帧；写入失败时断开软件连接，不能保证固件已收到停止。位置目标的 ±180° 范围不代表机械安全范围。默认 `moveTo()` 继续使用已确认的速度协议；原生角度、速率、休眠/唤醒和额外状态放在显式研究配置中，本机尚未验证。四元数转换不自动假定设备坐标；保存位置返回不等于固件单轴回中。自动重连默认关闭，即使启用也不恢复旧运动。

[非相机能力边界](docs/CAPABILITIES.md) 列出已实现、实验接口及仍缺少本机协议依据的功能。不能将本版本称为“全部蓝牙能力完整支持”。

源码以 MIT 许可提供，与 DJI 无官方隶属关系。设备 ID、原始抓包、依赖和生成应用不提交 Git；当前没有进行 npm 发布或二进制发布。


当前 App 来源参数 SDK 提供显式配置下的参数读取和跟随灵敏度读写，复用既有连接。调用入口、各端差异与未验收边界见 [参数 SDK](docs/APP_COMMANDS.md)。全部底层命令仍未完成，高级功能开发继续暂停。


0.7.4 新增显式当前App来源的自定义跟随与电机设置位字段读取/修改；保留其他位、共享事务截止时间和操作槽。入口及未验收边界见 [命名设置SDK](docs/APP_SETTINGS.md)。


0.7.5 封装当前型号路径的无ACK自动调参请求、校准状态查询/通知，严格区分本机写入、设备报告与物理完成。接口和待验收边界见 [调参请求与状态](docs/APP_CALIBRATION.md)。


0.7.6新增十二个命名电机数值参数的31/32读写，和普通用户参数命令空间分开；源码范围与实际设备效果分别验收。见 [电机参数SDK](docs/APP_MOTOR_TUNING.md)。

平衡测试新增静态证据：[调用链与同名参数冲突](tools/research/BALANCE_TEST.md)。运行时版本未变，尚未新增该SDK接口或硬件验收。

0.7.7新增显式来源的平衡测试启动请求与三轴结果读取，见 [平衡测试SDK](docs/APP_BALANCE_TEST.md)；尚无实机验收。

0.7.8新增与自动调参分开的system_calc自动校准请求/状态，见 [APP_SYSTEM_CALIBRATION.md](docs/APP_SYSTEM_CALIBRATION.md)，尚未确认水平校准身份或实机效果。


多段恢复续报：已严格恢复6段49,542条code_item，原business05哈希不变；另外2段未恢复，模式UI语义仍需核对。见 [CODE_BANKS.md](tools/research/CODE_BANKS.md)。运行时保持0.7.8/0.3.8，无新增发送或硬件操作。
