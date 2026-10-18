# rs4mini-ble-controller

通过电脑 BLE 直接控制 DJI RS 4 Mini 的非官方项目。Node.js **0.7.29** 为主实现；Python/Web **0.7.29**、macOS 原生面板 **0.3.29** 提供三轴速度、姿态/机械关节反馈、低速定位、轨迹与路点、保存位置返回和显式自动重连。相机控制和视觉跟踪不属于当前范围。

**当前状态：底层 SDK 已增加当前 App 参数事务、调参请求与状态封装；全部非相机 BLE 能力仍未完成。**
完成项、验证证据与后续接手入口统一保存在 [项目状态](docs/PROJECT_STATUS.md)。

0.7.11增加[独立配置输入源与数值SDK](docs/APP_STANDALONE_TUNING.md)：六项参数、显式输入源2同包写入，读取保留实际输入源。尚无实机验收。

最新[预设与模式研究](tools/research/PROFILES.md)区分配置、运动预设和工作模式，确认HG724条件新列表不能套用旧PF/PTF编号；尚未据此新增接口。

最新[订阅与推送包层研究](tools/research/SUBSCRIPTIONS.md)区分CENTER/id7无ACK订阅、本地取消与源预设推送偏移；尚无本机效果或新接口声明。

0.7.12新增[固定用户参数被动解码](docs/APP_USER_PARAMETERS.md)，17项源码字段与独立缓存，不发送订阅，不代表本机活动预设确认。

最新[微调、手柄与重置研究](tools/research/FINE_HANDLE_RESET.md)核对66方法与型号继承，区分真实轴值、FF对象默认、手柄缓存回退及HG724重置载荷；SDK进度见下文。

0.7.13新增[手柄参数只读查询](docs/APP_HANDLE_SETTINGS.md)，保留8个源字段原值与额外字节，不增加设置写入。

0.7.14增加[Pitch/Roll微调请求](docs/APP_FINE_TUNE.md)：源码float32编码、独占至ACK，实际效果和暂停状态未验收。

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

| 功能 | Node 0.7.29 | Python 0.7.29 | Web 0.7.29 | macOS 面板 0.3.29 |
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
| 显式App来源的手柄状态候选 | 被动SDK快照 | 被动SDK快照 | 共享JS快照 | 被动SDK快照 |
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

0.7.9新增六组跟随/摇杆按轴档位读改写，保留其他轴与未解释低两位，见 [APP_FOLLOW_MODES.md](docs/APP_FOLLOW_MODES.md)。尚无实机验收，不是PF/PTF/FPV预设。


数值参数静态续报：[普通18项与独立配置分支](tools/research/NUMERIC_PARAMS.md)。已核对有效继承、缺省读取模型及1/2字节编码，独立配置由App与输入源2同包写入。本批尚未新增这些SDK接口，运行时保持0.7.9/0.3.9。

0.7.10新增18项普通跟随/摇杆数值读写，保留未知无符号读值并明确活动预设未验证，见 [APP_NUMERIC_TUNING.md](docs/APP_NUMERIC_TUNING.md)。

手柄单字段请求见 [APP_HANDLE_WRITE.md](docs/APP_HANDLE_WRITE.md)，实际设备/FF语义尚未验收。

0.7.16新增[HG724恢复设置请求](docs/APP_FACTORY_RESET.md)，仅源分支与ACK封装，恢复范围和本机实际效果未验收。

新增[保存命令六段引用审计](tools/research/SAVE_CALLERS.md)，扩大检索范围，仍缺HG724业务调用证据，未新增保存接口。

新模式调用链已追至[参数17/18/19与轴模式34](tools/research/PROFILES.md)，与现有132/35位设置分开；完整切换事务和本机效果尚未验收。

0.7.17新增[轴模式34命名读写](docs/APP_AXIS_MODE.md)，源枚举与未知位分别保留，完整跟随模式/本机效果未验收。

0.7.18新增[普通跟随轴17/18/19读写](docs/APP_SMOOTH_TRACK.md)，未指定字段省略、异常值保留，完整模式/实机效果未验收。

0.7.19新增[配置0与工作模式62命名读写](docs/APP_PROFILE_VALUES.md)，未知原值保留，未确认活动预设/完整跟随模式或本机效果。

新增[六段命令引用矩阵与0D边界](tools/research/COMMAND_REFERENCES.md)，区分枚举名、实现候选与型号/硬件证据，不新增试探发送。


最新[原生角度控制研究](tools/research/ANGLES.md)已区分04:0A两种布局与HG724继承rotate的04:14路径；能力/地址/暂停及物理完成仍待核对，未新增当前App角度发送接口。


后续[角度能力与包上下文研究](tools/research/ANGLE_CONTEXT.md)核对初始化覆盖、接收ID传递及EYE两个不同重载；本机地址、依赖适用性/恢复与物理完成仍未验收，没有新增发送。


[暂停状态与等待依赖审计](tools/research/STABILIZATION_DEPENDENCY.md)区分源stabilization状态、3秒等待与真实云台停止/到位；关闭也返回paused、等待不按请求序号关联，未新增运行时功能或声明本机支持。


[回中平台分支与App入口研究](tools/research/RESET_ROUTES.md)已区分通用SpecialControl流程和三处直接FE01源分支；现有实测回中保持不变，未开放其他模式或混合控制发送。


0.7.20新增[手柄状态被动候选](docs/APP_HANDHELD_STICK.md)，仅显式App来源、无58发送/订阅，真实57布局、单位与轴映射等待本机验收；未新增高级功能。


0.7.21新增[异常与电量被动候选](docs/APP_SOURCE_STATUS.md)，显式App来源、原始位/255保留，不触发请求或自动控制；本机布局与通知仍未验收。


[教程命令源审计](tools/research/TUTORIAL.md)记录未知步骤回退与32位移位边界；未定位HG724业务入口，不新增教程发送或以教程标志判定运动完成。


[HG724支持键规则研究](tools/research/KEY_SUPPORT.md)区分声明支持谓词、缓存动作注册与原生BLE命令；保留多匹配歧义，不据键数量声明协议完整或新增发送。


[HG724初始化与动作声明分派](tools/research/REGISTRATION.md)补齐继承目录及两个动作的静态声明链，仍非运行时注册或本机验收；不改变SDK发送与高级门槛。


[固件动作程序通用源审计](tools/research/PROGRAMS.md)核对62/25/37/63请求与38/64/6B状态差异；仅静态业务体证据，尚无HG724完整路径或SDK新增发送，全命令门槛false。


[程序菜单与HG724条件分类](tools/research/PROGRAM_ENTRY.md)补齐产品缓存/布局声明链，区分快门线帮助与检查函数可达性；尚未证明完整型号工作流，不新增发送或高级功能。


[主页面挂载与轨迹UI工作流](tools/research/TRACK_WORKFLOW.md)补齐静态挂载链，区分ACK后的界面状态、重订阅和物理停止；仍未开放程序SDK或高级功能。


[程序基础接收路径](tools/research/PROGRAM_RECEIVE.md)区分ACK返回码与业务首字节、6B双路分派及扩展命令表边界；仅静态研究，不新增SDK发送或高级功能。


0.7.22新增[程序状态被动候选](docs/APP_PROGRAM_STATUS.md)：显式App来源下38/64/6B独立帧快照，未知/重复记录保留，无查询/订阅/自动ACK，不等于物理完成；完整命令仍未验收。


0.7.23新增[单次程序状态请求](docs/APP_PROGRAM_REQUEST.md)：显式App来源、固定type2与三个命名程序，仅关联ACK、业务体不透明；不承诺新通知，不增加连续订阅或动作执行，本机未验收。


0.7.24新增[程序状态推送启停请求](docs/APP_PROGRAM_SUBSCRIPTION.md)：显式program与布尔enabled，固定type0/1及关联ACK；不证明远端订阅状态、不自动维护或恢复订阅，不发送动作程序命令。本机仍未验收。


新增[轨迹路点与ActualPose审计](tools/research/TRACK_POINTS.md)：UI秒数分段、首点/Roll规则及04:66缓存来源已核对，不能把原生轨迹角度直接当作现有机械关节角。仅研究，无SDK发送或硬件操作，运行时仍0.7.24/0.3.24，全命令门槛false。


0.7.25新增[外设状态源候选](docs/APP_PERIPHERAL_STATUS.md)：46源类型/43 getter视图、保留tag21碰撞和GPS整数截断；不改现有姿态/关节，不自动ACK/订阅或控制，本机未验收。


新增[完整订阅键与初始化条件审计](tools/research/SUBSCRIPTION_CATALOG.md)：152个注册键分开记录显式索引、21个元数据条件键与2个型号条件；不将缺失0或资源预期索引自动变成SDK发送表。仅离线研究，运行时仍0.7.25/0.3.25，全命令门槛false。


## 订阅初始化审计（2026-10-18）

固定六段13方法审计确认元数据异步加载、逐项发布与BaseCommand构造时一次性捕获；不能推断真实调度、竞争或捕获0。独立SDK可明确选择固定DB已加载的索引分支，无需依赖App缓存；本机路由/通知/远端取消仍未验证。见[SUBSCRIPTION_INIT.md](tools/research/SUBSCRIPTION_INIT.md)和证据protocol/research/ronin-subscription-init-evidence.json。两次实际提取JSON逐字节一致，新增7项研究测试。此研究检查点不发布新的运行时版本；已提交运行时仍0.7.25/0.3.25。单次订阅SDK正在工作树中开发，尚未交付，不计作已完成；全命令与高级门槛仍false，无硬件或厂商执行。


## 0.7.26单次命名参数订阅 / 原生0.3.26 build29

显式App来源下发送固定DB已加载/HG724静态分支的152命名键非空单次04:12请求，CENTER/id7、无ACK；报告21元数据和2型号条件键。不提供空集停止、后台刷新、反向请求或重连重放；三条中位前导及独占操作槽，不由发送成功判断远端订阅、通知新鲜度或物理效果。详见[单次参数订阅](docs/APP_PARAMETER_SUBSCRIPTION.md)。此版本扩展此前“仅研究/工作树开发”的历史状态；实际型号/路由/通知/远端停止仍待验收，全命令及高级门槛false，无硬件/实时UI/厂商执行。


## 外设数据04:69源审计（运行时不变）

固定六段36方法、12数据类型/4来源枚举，核对tag2的控制来源及三轴signed16原值、无ACK start、空doPack和基础双路分发。仅定位跟踪界面读取两轴的一个直接调用者，无HG724或物理单位/路由证据。源旧字段保留/短包只清速度与离线独立帧视图区分；未增加SDK收发、相机/视觉或高级功能。见[EXTERNAL_DEVICE.md](tools/research/EXTERNAL_DEVICE.md)和protocol/research/ronin-external-device-evidence.json。运行时仍0.7.26/0.3.26，全部命令及高级门槛false，无硬件/实时UI/厂商执行。


## 0.7.27外设数据被动候选 / 原生0.3.27 build30

显式App来源下externalDeviceStatus/kind=externalDevice解析04:69完整TLV，tag2保留来源及三轴signed16原值、未知/重复与尾字节；Other7与未知原值分开，不继承源单例旧值或短包清零副作用。来源/断线清空，观察者隔离；不发送/订阅/自动ACK，不完成查询或改变姿态/关节、运动所有权。见[外设数据候选SDK](docs/APP_EXTERNAL_DEVICE_STATUS.md)。本机布局/单位/参考系均未验收，未新增相机/视觉/高级功能，无硬件/liveUI/厂商执行，全命令门槛false；此前“仅研究未接SDK”为历史状态。


## 校准08/30域与近似类绑定研究

固定六段48方法、17直接调用、9类型化声明/9枚举引用，确认04:30实际绑定SensorCalibrateStatus而非近似AutoCalibrationStatus；30状态COMPLETE0/PROCESSING1/FAIL3/OTHER9，与08响应FAIL0/SUCCESS1/PROCESSING2分开，不复用bool inProgress或system_calc表。08单字节部件及ACK业务偏移已核对，型号入口/实际扩展、路由/物理中止仍未完成。详见[校准源审计](tools/research/SENSOR_CALIBRATION.md)及protocol/research/ronin-sensor-calibration-evidence.json。仅离线研究，运行时0.7.27/0.3.27不变，没有SDK收发、相机/视觉/高级新增或硬件/liveUI/厂商执行，完整命令门槛false。


## 0.7.28传感器校准被动候选 / 原生0.3.28 build31

显式App来源下sensorCalibrationStatus/kind=sensorCalibration解析04:30两字节源进度/状态及尾部，保留0..255原值，映射0/1/3/9并标记未知；不复用08状态或旧inProgress，不补短包默认，不由COMPLETE结束查询/运动。缓存复制/不可变、观察者隔离、来源/断线清空。见[传感器校准候选SDK](docs/APP_SENSOR_CALIBRATION_STATUS.md)。没有查询/订阅/自动ACK/校准触发或相机/视觉/高级新增；本机/单位/请求关联与物理完成未验收，无硬件/liveUI/厂商执行，全命令门槛false。此前当前App30“未接SDK”限定为历史状态。


## 校准入口条件与HG724静态分支研究

63方法/2布局核对SystemStatus→新设置构造链、普通GYRO05/高级AUTO00的04:08及MotorEnabled缓存门槛。所选项与ModelName均HG724的显式源码情形中，普通隐藏/高级显示且旁路版本；阈值00.02.32.25严格大于、缓存/异步可见性与实际设备分开。高级ACK后60秒本地计时和百分比显示不证明固件中止/请求关联。见[校准入口研究](tools/research/CALIBRATION_ENTRY.md)及protocol/research/ronin-calibration-entry-evidence.json。不与system_calc/index36混用，未新增SDK收发/高级功能或硬件/liveUI/厂商执行，运行时仍0.7.28/0.3.28，完整命令门槛false。


## 0.7.29接收业务解析边界 / 原生0.3.29 build32

关联App ACK、04:05反馈、04:6E调参通知和旧研究状态拒绝加密/无效flags，原始帧保持可观察；加密读取不推进参数写入，加密关节不进入定位反馈。没有新增命令、解密、协商、硬件操作或高级功能，完整命令与高级门槛仍false。契约见 docs/PLAINTEXT_BOUNDARIES.md（仓库根目录）；本版本取代此前宽松解析行为，历史版本记录保留。


## 校准默认包头与条件加密研究

固定六段28方法审计确认04:08新对象默认APP/id0→GIMBAL/id0、条件加密前flags40；NEEDACK.YES线上值2不是ordinal。通用发送层可按可变会话策略加密包括命令集/命令号的区间；接收事件关闭仍可能运行分类分支，不把业务Encrypt.NO当最终线上保证。见[校准传输审计](tools/research/CALIBRATION_TRANSPORT.md)（仓库根目录）及protocol/research/ronin-calibration-transport-evidence.json。未实现/执行JNI或APK、未新增SDK收发/高级功能、没有硬件或实时UI，运行时仍0.7.29/0.3.29，完整命令门槛false。
