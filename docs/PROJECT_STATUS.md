# 项目状态与接手入口

更新日期：2026-10-17。当前源码检查点为 Node/Python/Web **0.7.12**、macOS 原生面板 **0.3.12**。

**当前 App 参数事务已进入四端设备 SDK；全部非相机 BLE 能力整体目标尚未完成。**
用户已要求将源码与相关信息提交至 GitHub。本记录随源码版本保存，提交和远端状态以 Git 历史为准；
这不是 npm 发布或 GitHub 二进制 Release。

## 当前进度：0.7.12 固定用户参数被动解码

四端显式App来源增加04:24的17个getter原值、userParameterStatus独立快照和kind=userParameters事件。完整已知布局不少于74字节，限定未加密请求型和端点；短帧不补零，未知枚举/字节保留。20方法源码审计、三端目录逐项匹配。Node131/Web14/Python两环境各108/native91+124+3/research两环境各71，类型/边界/构建与安装包回归通过。没有订阅发送或活动预设确认，本机布局和全部协议仍未完成。见 [APP_USER_PARAMETERS.md](APP_USER_PARAMETERS.md)。下方为历史进度。

## 最新研究：参数订阅与推送包层

新增34方法审计，04:12为CENTER/id7无ACK，按命令号/最高频道/位图分组；本地引用计数、1秒刷新和临时get的3秒移除不证明远端TTL或停止。源未加密请求型04:24的payload偏移2已追通，与04:10订阅参数响应分开。见 [SUBSCRIPTIONS.md](../tools/research/SUBSCRIPTIONS.md)。研究67项在两个Python环境通过，固定APK独立复现一致；统一离线检查通过。本批未开放SDK接口或操作硬件，运行时仍0.7.11/0.3.11，全协议和高级门槛仍false。

## 最新研究：预设与模式的不同路径

新增26个方法指纹，核对table_choice/index0、工作模式index62、独立的MovementSettingsProfile及getPresetID业务读取上下文。HG724条件分支与设备选择列表均走新模式路径，列表只有FPV/Custom/3D Roll 360，不能移用旧PTF/PF编号；新路径模式下拉还受UserProfile=2条件约束。见 [PROFILES.md](../tools/research/PROFILES.md)。研究58项在两个Python环境通过，固定APK实际复现一致；统一离线检查通过。本批未新增SDK/UI接口或硬件证据，运行时版本和完整性门槛不变。

## 当前进度：0.7.11 独立配置输入源SDK

四端新增get/setStandaloneTuning，六项数值与输入源2同一0F请求，要求调用方显式输入源；10读取保留实际inputSourceRaw与异常数值，不自动切预设或源。型号条件分支已静态关联到产品Model.HG724，不是实机读数。完整契约见 [APP_STANDALONE_TUNING.md](APP_STANDALONE_TUNING.md)。Node126/Web14/Python两环境各103/native87+119+3/research两环境各54，类型/边界/构建及安装包回归通过。未操作硬件/UI、未新增高级任务；全部命令与实机验收仍未完成。下方为历史记录。

## 当前进度：0.7.10 普通数值SDK

四端get/setFollowTuning与get/setRcTuning提供18项普通跟随/RC数值读取与单项写入，宽度和范围逐项绑定源码，保留未知无符号原值。单次写入独占到ACK，无自动重发或切预设/输入源；activePresetVerified:false，型号/真实效果仍待验收。见 [APP_NUMERIC_TUNING.md](APP_NUMERIC_TUNING.md)。三端目录逐项和源码比对；Node120/Web14/Python各97/native83+113+3/research53，类型/边界/构建通过。无硬件/UI或高级新增，独立配置、预设验证及全部命令仍未完成。下方为历史记录。

## 最新研究：数值参数与输入源分支

已核对18项普通跟随/RC数值记录、有效继承/枚举命令映射、缺省DataGimbalGetUserParams模型和1/2字节小端编码。另6个独立配置字段在App分支中与input_source=2同包写入，不能当普通RC字段别名。见 [NUMERIC_PARAMS.md](../tools/research/NUMERIC_PARAMS.md)。本批是静态证据和复现工具，42方法指纹、两个Python环境研究各53项通过，尚未新增这些SDK接口或发送。运行时仍0.7.9/0.3.9，无硬件/UI操作，两项完成门槛仍false。

## 当前进度：0.7.9 跟随/摇杆按轴档位

四端get/setFollowSettings、get/setRcSettings封装六组命名参数：跟随速度/加速度/死区，摇杆速度/死区/平滑。SDK与UI两段核对轴位和custom/low/middle/high枚举；写入以新鲜读取保留其他轴和低两位，一次所有权与总截止时间贯穿读取/ACK。见 [APP_FOLLOW_MODES.md](APP_FOLLOW_MODES.md)。无硬件/UI或高级新增，PF/PTF/FPV完整预设、custom数值等仍待补齐。Node113/Web14/Python各91/native79+107+3/research49，类型/边界/构建通过，全命令与高级门槛仍false。下方为历史记录。

## 最新研究：多段代码恢复与模式调用方

已从固定APK严格恢复6段49,542条原code_item，原business05哈希不变；段01/07仍未恢复。新business03定位40个跟随/摇杆模式键UI引用方法，出现两位字段打包线索，不能把整字节当作单轴值。详见 [CODE_BANKS.md](../tools/research/CODE_BANKS.md)。本批未新增SDK发送或高级功能，运行时仍0.7.8/原生0.3.8；研究48项在两个Python环境通过，无硬件/UI操作，两个完成门槛仍false。

## 当前进度：0.7.8 system_calc自动校准

四端提供sendAutoCalibrationRequest/getAutoCalibrationStatus（原生等价方法、Python别名），普通0F/10命名参数index36/size1，启动固定1。状态0 DEFAULT/1 START/2 FAIL/3 SUCCESS与写入范围分开，未知值保留；和6A/6E自动调参不混用，无自动轮询/等待完成或虚构中止。见 [APP_SYSTEM_CALIBRATION.md](APP_SYSTEM_CALIBRATION.md)。尚未确认水平校准身份、本机接受/完成/停止。Node108/Web14/Python各86/native75+101+3/research45，类型/边界/构建通过。无硬件/UI操作，全协议和高级门槛仍false。下方为历史记录。

## 当前进度：0.7.7 平衡测试请求与结果

四端提供sendBalanceTestRequest/getBalanceTestStatus（原生等价接口），普通0F/10命名参数index37，启动值固定64。保留原值、零结果为null，无任意参数写入或虚构中止；ACK后释放主机槽，固件完成/停止仍未实机验收。见 [APP_BALANCE_TEST.md](APP_BALANCE_TEST.md)。没有硬件/UI操作，全命令及高级门槛仍false。Node102/Web14、Python各80、原生72+94+3、研究42；类型/边界/构建通过。下方为历史记录。

## 当前进度：0.7.6 命名电机参数

沿当前App命名调用链封装31/32空间中的十二个电机数值字段：三轴刚度、强度、陀螺仪滤波和PreControl。源码资源、INT08U类型、单项/数组打包分支及低字节顺序已核对；和普通用户参数0F/10空间分开，不按索引猜名字。契约与限制见 [APP_MOTOR_TUNING.md](APP_MOTOR_TUNING.md)。

离线结果：Node96、Web14、Python各74、原生69+88+3、研究38；类型/边界/构建通过。没有硬件或UI操作；本机接受/生效/持久化未验收，平衡测试、水平校准及其余命令继续推进，完整性和高级门槛保持false。下方为历史版本记录。

## 当前进度：0.7.5 调参请求与状态

沿HG724→HG702的覆盖实现封装04:6A无ACK调参请求，以及04:6E状态查询和通知。发送、返回码、设备报告及物理完成分别处理，没有新增高级程序等待任务。完整接口见 [APP_CALIBRATION.md](APP_CALIBRATION.md)。

离线检查：Node90、Web14、Python两个运行时各68、原生65+83+3、研究37；类型/边界/构建通过。Node0.7.5 tarball安装后90、Python0.7.5 wheel隔离安装后68通过。没有扫描、连接、移动设备或启动UI。全命令和高级门槛仍false，电机数值/水平校准/平衡测试及其他协议继续审计。下方为各历史版本记录。

## 当前进度：0.7.4 命名设置位字段

显式当前App来源SDK增加自定义跟随启用/三轴与电机启用/禁止自拍/禁止竖拍/360°Roll设置，沿HG724继承链封装源码语义；不声称固件或UI支持。按当前读值修改指定字段，保留其他位；读写持续占用操作槽并共享单调时钟总截止时间，取消或读失败不继续写。见 [APP_SETTINGS.md](APP_SETTINGS.md)。

离线验证：Node83、Web13、Python两个运行时各61、原生58+74+3、研究35，类型/边界与构建通过。Node0.7.4 tarball安装后83、Python0.7.4 wheel隔离安装后61通过。全命令和高级新增门槛保持false，没有操作硬件或新增高级功能。下方各阶段及安装包数据是历史，以版本区分。

## 当前进度：0.7.3 参数事务

新增显式 `ronin-2.2.2` 来源参数读取、HG724 跟随灵敏度0/1读写和 ACK 校验，入口继续为应用的 `RS4Mini` / `RSGimbal`。没有任意参数写入或新增高级功能，没有操作硬件。契约见 [APP_COMMANDS.md](APP_COMMANDS.md)。

本轮离线结果：Node76、Web13、Python3.8/3.12各55、原生54+68+3；研究32项，TypeScript、模块边界与原生构建通过。Node0.7.3 tarball隔离安装后76项、Python0.7.3 wheel隔离安装后55项通过；旧版交付与历史验证另列下方。

静态审计固定55类/631方法（含 Ccode）；通用代码可读不代表全部HG724调用链或型号支持。继续审计和封装其余命令，完整性门槛保持false。下方0.7.2记录是历史，最新说明优先。

## 架构边界（2026-10-16）

用户进一步要求区分蓝牙设备 SDK 和基于 SDK 的运动组合。归属、姿态/关节含义及剩余需求的可行性已固定在 [ARCHITECTURE.md](ARCHITECTURE.md)。
两层运行时模块已拆分；应用仅使用高级 `RS4Mini` / `RSGimbal` 对象，基础方法也通过它访问底层。
用户新增前置条件：全部设备命令解析与封装验收完成前，不再新增高级功能。该条件目前尚未满足，见 [SDK_COMMANDS.md](SDK_COMMANDS.md)。
设备协议能力与软件任务分别验收，不能用上层功能数量衡量新增 BLE 指令数量。

## 已完成的源码范围

- 三轴速度、停止、三轴回中；姿态与机械关节反馈解码；`getAttitude()`、`getJointAngles()`、`moveTo()`。
- 生命周期截止时间、运动互斥与取消、故障清理；显式启用的有界自动重连，重连后不恢复旧运动。
- 速度关键帧轨迹、关节路点与停留、保存位置和按轴返回；显式分量顺序的四元数数学转换。
- Python、Web 和原生面板已按各端方式接入；API、可配置项与查询并发语义存在差异，见根 README 和各端说明。
- 显式 `rs3`/`rs3mini` 研究配置下的限定查询、休眠/唤醒、原生角度/速率及被动状态解析。
  来源是其他型号，尚无本设备兼容性证据；普通 `moveTo()` 继续使用已确认的速度帧加关节反馈。

## 验证证据

| 验证 | 本地结果 |
|---|---|
| Node | 69 项生命周期/运动/扩展测试，另有协议与遥测检查 |
| Web | 12 项模拟 GATT 与页面事件检查 |
| Python | 3.8.10/Bleak 0.22.3 和 3.12.13/Bleak 1.1.1，各 48 项 |
| macOS | 48 项纯核心、57 项假设备和 3 项独立设备 SDK 断言；面板与探针构建及 ad-hoc 签名通过 |
| 类型与安装包 | TypeScript 5.9.3 strict/NodeNext；Node tarball 安装后 69 项、Python wheel 安装后 48 项通过 |

离线复现入口是 `sh tools/check-offline.sh`；安装要求见根 README。
静态研究工具另有 4 项合成边界测试通过。
源码提交 `f15ba51` 的 [GitHub Actions 独立检查](https://github.com/Ran-ying/rs4mini-ble-controller/actions/runs/38867602073) 已成功；后续提交以各自运行结果为准。
详细证据和历史实机读数见 [VALIDATION.md](VALIDATION.md)。

0.5.0 部署后的真实连接采样成功（5 秒、5 帧、约 1 Hz）。历史版本有分轴低速定位记录，
但不为新版本的取消、轨迹、断线恢复或多轴运动背书。用户离家后没有扫描、连接或移动设备；
新 UI 可视检查也未完成。

## 未完成项与下一步

1. 按 [HARDWARE_CHECKLIST.md](HARDWARE_CHECKLIST.md) 进行统一实机和可视验收，登记固件、模式、负载、
   平衡、系统/运行时、目标与到位/停止后的读数。用户返回并要求测试之前，不操作硬件。
2. 补充真正单轴回中、跟随模式、校准/电机调参、固件原生轨迹/全景等协议依据与实现。
   保存位置按轴返回不等于固件单轴回中，软件轨迹不等于固件原生轨迹。
3. 受控验证其他型号实验配置与本机的兼容性；确认四元数顺序、坐标约定和更多状态字段。
   没有证据的部分继续标记未知，不从离线测试或候选类名推断兼容。

约 1 Hz 反馈、经验角速度换算、BLE 停止的物理效果与机械精度均有适用限制，
不能据此宣称全部蓝牙能力或全负载精度已经实现。相机/视觉仍不在范围内。

## 长期维护入口

- [AGENTS.md](../AGENTS.md)：用户决定、协议约束、测试与仓库卫生。
- [CAPABILITIES.md](CAPABILITIES.md)：已实现、实验支持和缺口的功能矩阵。
- [EXPANSION_PLAN.md](EXPANSION_PLAN.md)：当前扩展计划；[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) 为 0.6.0 历史阶段。
- [PROTOCOL.md](PROTOCOL.md)、[RESEARCH_NEXT.md](RESEARCH_NEXT.md)：协议证据和研究线索。
- [Node API](../node/API.md)、[变更记录](../node/CHANGELOG.md)：主实现公共契约与版本变更。

只提交可维护源码、合成测试与匿名结果。设备 ID、原始抓包、凭据、依赖、生成应用、
外部研究仓库和 Ronin APK 不进入 Git。后续验收有新证据时，同步更新本文件、协议/能力表和验证记录。

## 0.7.2 底层研究增量

官方 APK 中 8 段隐藏 DEX 的 6 段已能结构化读取元数据，得到 43 项命令枚举和两份参数表线索。
关键方法仍为保护桩，不能从枚举或参数名直接生成设备写入。命令清单扩充到 48 条，仍不完整。
SDK 仅增加研究配置下的被动参数响应原始结构解析；没有新增发送命令或高级功能。
工具与证据固定在 `tools/research/`、`protocol/research/`，协议与本机验收条件仍未通过。


## 后续底层研究（2026-10-16，运行时版本未变）

官方 MSDK provided 4.18 的只读交叉研究获得旧版回中/模式、参数索引请求及手柄参数业务体候选。
发现旧轴枚举与本机 FE01 效果有差异，也确认包层返回码可能在进入业务解码前被剥离。
增加可复现提取器和纯离线候选载荷工具，未修改任何 SDK/UI 运行时或发送允许列表；命令清单仍为 48 条，完整性条件仍为 false。
工具说明与不适用边界见 [MSDK_V4.md](../tools/research/MSDK_V4.md)。


## HG724 型号与参数资源关联（2026-10-16）

可读 App 指令已把展示名 DJI RS 4 Mini 与 BLE 前缀 dji rs4 mini- 关联到 HG724。
HG724 类型枚举值 103 仅为 App 事实，不是已解码线上字段或本机查询结果。
专属类注册 FollowModeSensitivity，但设置方法与参数加载仍为保护桩，未恢复具体命令/索引/载荷。
两份资源原名分别为 gimbal_param_infos（res/DB.json）和 ronin2_gimbal_param_infos（res/jy.json），
不能据资源名或继承关系认定本机采用哪一份。完整证据与复现见 [HG724.md](../tools/research/HG724.md)。
本轮只增加离线研究工具，SDK/原生版本、48 条清单及完整性门槛不变，没有硬件操作。


## 当前 App 原代码备份恢复（2026-10-16）

在 classes6/business-05 的 fdex/dgc2 尾部发现原始代码备份，19,436 条记录逐一匹配方法 code_off 槽位、完整长度和指令单元数，恢复为不执行的离线视图。
HG724 跟随灵敏度 setter、参数管理器读取 gimbal_param_infos 的路径及参数写入打包已可读：命名参数 cmd_follow_mode_sensitivity 为 index150/size1，04:0F 源码载荷为 960100 或 960101。
当前复位命令确认是 mode+布尔 reset，而非旧 SDK 按轴枚举。本轮只添加恢复与离线核对工具，未新增 SDK/UI 发送或解码接口，也没有操作硬件；整个协议和本机验收仍未完成。
复现、指纹、适用范围与剩余缺口见 [CODE_RESTORATION.md](../tools/research/CODE_RESTORATION.md)。此前“setter/加载仅见保护桩”的记录属于旧 metadata-only 阶段。


## 平衡测试静态调用链补充

HG724继承的启动路径为普通用户参数04:0F，balance_test/index37/size1，启动值64；不是直接调用04:40。资源存在两条同名参数范围0..1和0..255，加载器按顺序名称覆盖，不能取第一条或假定名称唯一。状态/三轴结果位已定位，零结果字段不能当作通过。详见 [BALANCE_TEST.md](../tools/research/BALANCE_TEST.md)。本批是静态证据与复现工具，未新增SDK接口、发送或硬件证据；运行时仍0.7.6/0.3.6，两个完成门槛仍false。
