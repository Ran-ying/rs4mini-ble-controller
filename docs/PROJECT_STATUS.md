# 项目状态与接手入口

更新日期：2026-10-18。当前源码检查点为 Node/Python/Web **0.7.30**、macOS 原生面板 **0.3.30**。

**当前 App 参数事务已进入四端设备 SDK；全部非相机 BLE 能力整体目标尚未完成。**
用户已要求将源码与相关信息提交至 GitHub。本记录随源码版本保存，提交和远端状态以 Git 历史为准；
这不是 npm 发布或 GitHub 二进制 Release。

## 最新研究：完整订阅目录与初始化条件

24方法审计取得152不同注册键、DB-present情况下121命令/频道对和17组别名。21键的元数据缺失分支保留默认0，2键由组件缓存条件控制；HG724静态分支走默认true，不等于当前缓存或本机支持。见[SUBSCRIPTION_CATALOG.md](../tools/research/SUBSCRIPTION_CATALOG.md)。未新增SDK发送或高级功能，运行时仍0.7.25/0.3.25，资源加载顺序、路由与远端停止仍待补。

## 当前进度：0.7.25外设被动源候选

四端peripheralStatus/kind=peripheral覆盖46源类型、43 getter视图；保留tag21双解释、GPS整数截断、未知/重复及原始体，缺失不补零，不更新04:05姿态/关节或主机运动。见[APP_PERIPHERAL_STATUS.md](APP_PERIPHERAL_STATUS.md)。70方法源审计与SDK候选分开记录；未操作硬件，本机/全命令和高级门槛仍未通过。

## 最新研究：轨迹路点与ActualPose

新增51方法审计确认UI时间分段、ActualPose与MotorAngle分离、缓存到路点路径、首点及Roll规则；不能把现有关节反馈直接用作固件轨迹角度。见[TRACK_POINTS.md](../tools/research/TRACK_POINTS.md)。仅离线研究，运行时仍0.7.24/0.3.24，没有程序发送、订阅变更或高级新增；型号/物理参考系、相机隔离和全命令仍未验收。

## 历史进度：0.7.24 程序状态推送启停请求

四端新增显式type0/1、三个命名程序、严格布尔enabled及关联ACK；ACK业务体不透明，不证明远端订阅状态或持续通知。无自动续订/停止/恢复、动作程序或高级新增。见 [APP_PROGRAM_SUBSCRIPTION.md](APP_PROGRAM_SUBSCRIPTION.md)。全部命令和实机门槛仍未通过。

## 历史进度：0.7.23 显式单次程序状态请求

四端提供固定type2、三个命名程序的6B请求与关联ACK，ACK业务体不透明，不承诺新通知、不读旧缓存兜底；连续订阅及程序执行仍未开放。见 [APP_PROGRAM_REQUEST.md](APP_PROGRAM_REQUEST.md)。未操作硬件，完整命令和高级门槛仍false。

## 历史进度：0.7.22 程序状态被动候选

显式App来源下被动解析38/64/6B，独立快照、完整验长、未知/重复记录保留，不自动查询、订阅、ACK或触发程序。见 [APP_PROGRAM_STATUS.md](APP_PROGRAM_STATUS.md)。型号布局、实际通知和物理完成未验收，完整命令门槛仍false。

## 历史进度：0.7.19 配置0与工作模式62

命名请求与未知原值分别保留，不等同运动预设、完整跟随模式或本机活动预设。见 [APP_PROFILE_VALUES.md](APP_PROFILE_VALUES.md)。

## 历史进度：0.7.18 普通跟随轴开关

17/18/19读全部或单轴，写非空命名布尔子集并保留异常原值，不能当完整跟随模式或原子应用。见 [APP_SMOOTH_TRACK.md](APP_SMOOTH_TRACK.md)。

## 历史进度：0.7.17 轴模式34命名读写

源枚举/读取掩码与未知位已封装，其他位保留与本机效果未验收；不自动执行完整跟随切换。见 [APP_AXIS_MODE.md](APP_AXIS_MODE.md)。

## 历史进度：0.7.16 恢复设置源请求

四端封装显式HG724分支04:13/010001及关联ACK。取消/超时/断线不重放，范围、实际效果和持久化未验收。见 [APP_FACTORY_RESET.md](APP_FACTORY_RESET.md)。下方历史进度不代表本机验收或全命令完成。

## 历史进度：0.7.15 手柄单字段请求

四端新增sendHandleSettingRequest，限三个命名字段及0/1，其他字节源默认FF；源66方法审计与目录比对，NACK不转缓存成功，无自动回读/保存/回滚。FF与实际效果/持久化未验收，见 [APP_HANDLE_WRITE.md](APP_HANDLE_WRITE.md)。下方为历史进度，全部命令门槛仍false。

## 历史进度：0.7.14 Pitch/Roll微调请求

四端sendFineTuneRequest及别名/原生等价方法封装04:07源参数与轴2/0，独占到ACK，复制参数、可取消/超时且不重放/回滚。49方法审计补齐暂停标志来源和回调，实际角度/累加/暂停/持久化未验收，不自动发送视觉稳定命令。见 [APP_FINE_TUNE.md](APP_FINE_TUNE.md)。未操作硬件/UI或新增高级任务，全部命令与两项门槛仍未完成。

## 当前进度：0.7.13 手柄只读查询

四端getHandleSettings及别名/原生等价方法封装04:36空体、关联ACK和8字节业务getter；保留异常原值/bit0及额外字节，不混用profile、04:24缓存或写入语义。见 [APP_HANDLE_SETTINGS.md](APP_HANDLE_SETTINGS.md)。Node135/Web14/Python两环境各112/native94+126+3/research两环境各77，类型/边界/构建及安装包回归通过。新增源码继承证据不代表本机支持，微调/手柄写入/保存/重置仍未完成；无硬件/UI或高级新增，两门槛false。

## 最新研究：微调、手柄与参数重置

42方法审计确认微调轴cmd值0/2/4及Pitch/Roll继承路径、手柄8字节与FF对象默认/只重置6项、PlatformType.HG724重置010001。保存类空体但两段未见直接调用者，仍缺型号业务证据。见 [FINE_HANDLE_RESET.md](../tools/research/FINE_HANDLE_RESET.md)。研究工具本身无发送，SDK只读查询以顶部0.7.13进度为准；未操作硬件，其他动作及全部命令与高级门槛仍未完成。

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


## 0.7.14微调请求验证（2026-10-17）

Node141/Web14、Python3.8/3.12各119、原生98核心+130假设备+3独立SDK、研究工具两个环境各77通过。统一离线检查含类型、边界与构建通过；安装后的Node包141/Python wheel119通过。固定49方法审计独立复现与证据JSON逐字节一致。覆盖Pitch/Roll的float32截断、参数快照、互斥、关联ACK、错误响应、取消和超时无重放；实际效果、累加、持久化及暂停稳定状态仍未验收。

第二Python环境暴露旧轨迹测试依赖调度时序：首次写入前超时会正确地只有3帧中位，旧测试要求4帧。现用局部可控时钟分别验证首次写入前0+3帧和写入后1+3帧，保持精确清理与所有权检查，未修改运行时轨迹逻辑。没有扫描、连接、移动设备、实时UI或执行厂商代码；全部命令与高级新增门槛仍false。


## 手柄写入调用及失败回退审计（运行时仍0.7.14/原生0.3.14）

固定源码控制审计现66方法。HG724继承的三个手柄setter均新建DataGimbalSetHandleParams对象，仅设置一个字段：ControllerMode→dualChannelMode/0，PitchOrRollInverse→tiltDirection/1，YawInverse→panDirection/2。模式通过ControllerMode.value传递枚举值（含UNKNOWN255）；反向参数是布尔0/1。不能从PitchOrRoll的名字扩展出独立Roll开关。未指定字段沿新对象默认FF编码，固件是否保留仍未证实；不以读值重写所有8字段替代源语义。

对应写入成功回调仅报告null，不解码回读。失败回调没有直接上报原Ccode，而按ControllerMode/PitchInvertedControlEnabled/YawInvertedControlEnabled键调用DJISDKCache.getValue；这不是已证实的直接BLE读取。缓存取值回调Class.cast后使用if-ne比较对象引用，非Object.equals；非空结果中相同引用可回报成功，否则RESULT_FAILED；结果对象为空时直接返回、没有完成回调，取值失败则传递错误。不能复制为“写入失败也成功”，也不能据此声称固件写入接受或持久化。

读取ControllerMode的上层回调用values()[raw]数组下标，不是find(raw)；方向回调仅raw==1为true，不是bit0（raw3不等于true）。SDK现有getHandleSettings继续保留原值，不照搬源代码对异常值的数组风险，也不重解释既有结果。新增3项审计测试覆盖单字段新对象、禁止singleton/多字段/未构造、引用比较与错误分支变更。没有新增SDK发送、厂商代码执行或硬件操作；手柄写入SDK及本机验收仍待完成，两个完整性门槛false。


## 0.7.15手柄单字段请求 / 原生0.3.15 build18

四端设备SDK的sendHandleSettingRequest（Python snake别名）显式App来源下仅接受dualChannelMode/tiltDirection/panDirection单字段及整数0/1，8字节35体未指定字节为源默认FF。新对象/独立体，不全量读改写、不新增相机字段。参数停止前验证/快照，复用连接/队列/操作所有权至关联ACK；取消/超时无重放或回滚，NACK直接失败、不缓存兜底成功、不自动回读。结果unspecifiedByteSemanticsVerified/readbackVerified/persistenceVerified及既有设备/物理标志均false。FF实际含义、模式/方向效果、持久化待本机验收。见docs/APP_HANDLE_WRITE.md；没有高级新增或硬件操作，全部命令门槛仍false。


## 0.7.15手柄单字段写入验证（2026-10-17）

统一离线检查Node147/Web14、Python3.8/3.12各125、原生103核心+135假设备+3独立SDK通过；研究工具两个环境各80，类型/边界/构建通过。Node tarball隔离安装后147、Python wheel隔离安装后125通过。新增三个命名字段精确FF默认载荷、独立体、输入快照、非法参数/排除字段、互斥、关联ACK、NACK不缓存兜底、请求前后取消/超时无重放及Web无Buffer编码覆盖。三端命名字段目录与66方法审计逐项比对。

安装包验证发现旧轨迹成功测试依赖60ms真实调度窗口，忙碌主机可能提前结束只发一帧导致误报。Node/Python成功测试改用局部可控时钟，每个完整两段帧推进20ms，精确检查0/20/40ms三帧插值与三帧停止；运行时不变，既有超时/取消测试保留。统一和安装回归修正后均通过。没有扫描、连接、移动设备、实时UI或厂商代码执行，FF真实效果、持久化等待本机验收，全部命令门槛false。


## 0.7.16恢复设置请求 / 原生0.3.16 build19

四端sendFactorySettingsResetRequest（Python snake别名）需显式App来源和sourcePlatform HG724，固定04:13/010001；不是类型枚举103或其他平台空体。停止前验证/快照，复用连接/队列/操作槽至关联ACK。取消/超时/断线不重发、不自动保存/回读/回滚，重连不重放。ACK不证明恢复范围、持久化、重启或物理完成，相关标志false，不自动清零/改写反馈或参数。恢复范围也未证明仅非相机字段。68方法审计新增成功/失败回调，未解析完成。见docs/APP_FACTORY_RESET.md。没有硬件/liveUI/厂商执行或高级新增；全部命令仍未完成。


## 0.7.16恢复设置源请求验证（2026-10-17）

统一离线Node154/Web14、Python3.8/3.12各132、原生106核心+141假设备+3独立SDK、研究工具两环境各80、类型/边界/构建通过。Node tarball隔离安装154、Python wheel隔离安装132通过，导入路径核对为安装目标。固定APK的68方法审计独立复现与JSON逐字节一致，新增13成功/失败回调只转交对象/映射Ccode而无完成解析；三端010001源分支比对通过。

新增精确帧/显式源平台/拒绝类型枚举103与原始体、输入快照、操作互斥、错命令/NACK、请求前后取消、超时无重发、断连与重新连接无重放。Web共享无Buffer编码；原生被动推送不完成待处理reset，断连拒绝并且只有一条reset。没有扫描、连接、移动设备或执行恢复设置，没有实时UI/厂商代码执行/高级新增。实际恢复范围、生效、持久化、重启和本机接受仍待验收，全命令门槛保持false。


## 保存命令六段引用扫描（运行时仍0.7.16/原生0.3.16）

新增ronin_save_trace.py固定APK与六段恢复视图哈希，扫描banks0/2/3/4/5/6的指令引用，区分外部直接invoke、内部invoke、分配、class常量、命令枚举和字符串。逐段计数之和268232方法、254468个带code的方法、3463422条指令（不声明全局去重或全部原始方法已恢复）。只发现bank05的4个方法：命令枚举$values/<clinit>以及保存类getInstance/start；没有外部直接调用者，其他五段无保存相关指令/字符串表线索。

带code的方法不等于原始方法全部恢复，可能含剩余保护桩；1/7段未恢复，反射/动态/本机固件路径未排除。不能据扫描缺失宣称不支持保存，也不能据命令类/空体/ACK开放HG724保存接口。没有新增SDK发送或高级功能、厂商执行/硬件操作。见tools/research/SAVE_CALLERS.md与protocol/research/ronin-save-callers-evidence.json，全命令门槛仍false。


## 2026-10-17保存命令六段扫描验证

研究工具Python3.8/3.12各85项通过（新增5项分类/哈希预检）；全部六段固定输入实际扫描独立复现与证据JSON一致，序列化键顺序统一后逐字节一致。统一离线Node154/Web14/Python132/原生106+141+3、类型/边界/构建通过。BANKS源码固定哈希与既有银行证据逐项核对，4个引用方法无外部直接调用者，不等于未支持或全App审计完成。运行时仍0.7.16/0.3.16，不新增SDK发送、硬件/厂商执行或高级功能，两个完整性门槛false。


## HG724新模式实际参数与调用顺序审计（运行时仍0.7.16/0.3.16）

ronin_profiles_trace.py现40方法。新列表index2在UI入口清除IsCustomFollowMode后调用GimbalAxisMode ThreeDRoll360，直接跳过setTrackModeHG711；不能直接把index2传该内部函数。SDK继承轴模式setter用FLOWER_SPECIAL_CMD/index34/size1，枚举value<<3，ThreeAxis/TwoAxis/Roll360/ThreeDRoll360→0/8/16/24。UI实际选择仅ThreeAxis与ThreeDRoll360；与index35电机roll360位64不同，不能互换。

FPV(index0)在必要时请求退出360到轴模式0，关闭index132自定义bit0，随后同一普通参数请求把Yaw/Pitch/Roll SmoothTrack Enabled分别index17/18/19、size1置1。Custom(index1)必要时同样退出360，再开启132 bit0，界面轴选择来自既有custom轴缓存，不自动覆盖三轴。源setIsCustomMode只是UI字段赋值，无BLE请求。模式选择仍受源UserProfile2的UI条件限制，不能自动激活预设。

CacheHelper设置调用没有串联确认，UI回调成功更新延时显示标志、失败日志/Toast；没有后续参数写入或固件补偿。源函数调用顺序不是线上包序/ACK串行证明，多请求不等于原子切换。没有新增模式SDK/发送/高级任务或硬件/厂商执行；真正完成切换、部分失败/取消/恢复与本机生效仍待实现/验收。详见tools/research/PROFILES.md与protocol/research/ronin-profiles-evidence.json。


## 2026-10-17 HG724新模式链验证

40方法固定APK/SDK/UI审计独立复现与证据JSON逐字节一致，研究工具Python3.8/3.12各88项（新增3项分支单位/轴枚举移位边界）。统一离线Node154/Web14/Python132/原生106+141+3、类型/边界/构建通过。原生模式参数17/18/19/34、枚举0/8/16/24、index2跳转绕过普通轴开关、自定义控件无设备副作用及回调无链式参数写入已核对。没有新增SDK发送/高级任务、操作硬件或执行厂商代码，运行时与安装包保持0.7.16/0.3.16，完整模式切换及全命令验收仍未完成。


## 0.7.17轴模式34读写 / 原生0.3.17 build20

四端getAxisMode/sendAxisModeRequest（Python snake别名）在显式App来源下封装34/size1。四个源枚举写0/8/16/24，读(raw>>3)&3，保留raw/unknownBits=raw&0xe7及headerByte，modelLayout/activePreset/device/physical标志false。HG724 UI只定位ThreeAxis及ThreeDRoll360，不宣称全部四种固件支持。源setter整字节写，不擅自RMW或保留其他位，otherBitsPreservationVerified/persistenceVerified=false。参数快照、写先停主机运动并独占至ACK，取消/超时/断线无重放/回滚，NACK不缓存兜底；不自动写132、17/18/19、35或激活预设，不是完整跟随模式。Node/Python有限读并发与原生读占槽差异保留。见docs/APP_AXIS_MODE.md；未操作硬件/执行厂商代码/新增高级任务，全命令未完成。


## 0.7.17轴模式命名读写验证（2026-10-17）

统一离线Node162/Web14、Python3.8/3.12各140、原生113核心+148假设备+3独立SDK、研究工具两环境各88、类型/边界/构建通过。隔离安装Node tarball162/Python wheel140通过，Python导入路径确认为wheel目标。40方法源码独立复现与JSON逐字节一致；源事件FLOWER_SPECIAL_CMD读取右移3/掩码3及三端四枚举目录比对通过。

新增四种34写体、源读取未知位/原字节/headerByte、错参数/短体/NACK、显式profile/拒绝PF标签及原始值、参数快照/互斥、取消前不发/后不重放、超时/断连与重连无重放、Web无Buffer测试。原生查询沿用占槽/先停，Node/Python查询沿用有限并发。不自动组合132/17/18/19/35或预设，不承诺其他位保留。没有硬件/liveUI/厂商执行或高级新增，全命令门槛仍false。


## 0.7.18普通跟随轴开关 / 原生0.3.18 build21

四端getSmoothTrackAxes/sendSmoothTrackAxesRequest（Python snake别名）显式App来源下封装17/18/19、size1，默认读三轴/可过滤单轴，写非空命名布尔子集，一条0F按yaw/pitch/roll排序，未指定字段省略。源App直接参数数组路径已确认，本次未定位逐轴SDK setter；不将其不存在或本机支持当结论。读raw0/1→enabled false/true，其他→null，保留raw/header、sourceEnabled=(raw==1)与withinSourceRange，不按bit0或错误码丢值。参数快照/写先停/独占至ACK，取消/超时/断线无重放/回滚，重连不恢复请求；不自动写132/34/35/预设/输入源/保存，不是完整模式。atomicApplication/activePreset/modelLayout/device/physical/persistence相关标志false。见docs/APP_SMOOTH_TRACK.md；没有高级新增、硬件/厂商执行，全命令仍未完成。


## 0.7.18普通跟随轴验证（2026-10-17）

统一离线Node170/Web14、Python3.8/3.12各148、原生120核心+155假设备+3独立SDK、研究工具两环境各88、类型/边界/构建通过。隔离安装Node tarball170/Python wheel148通过，Python导入路径为wheel目标。40方法源码独立复现逐字节一致，三轴事件读取raw==1及真假常量、三个命名索引目录逐项核对。

新增完整/子集/单轴单帧载荷、默认/过滤读取、异常3/255的原值/三态/源解释、错参数/短体/NACK、空/非布尔/未知字段拒绝、嵌套字典快照、互斥、取消/超时/断连重连无重放及Web无Buffer覆盖。未指定轴省略，同包ACK不等于原子应用，不自动写其他域或组合完整模式。没有扫描、连接、移动硬件、实时UI、厂商执行或高级新增，全部命令与实机验收仍未完成。


## 0.7.19配置0与工作模式62 / 原生0.3.19 build22

四端getUserProfile/sendUserProfileRequest、getWorkMode/sendWorkModeRequest（Python snake别名）显式App来源下独立读写0/62、size1。配置源范围0..5，源UI名仅0/1/2=M1/M2/M3，其他不推断运动预设；工作写仅精确Free/Flower/Fpv/Center四枚举，读取未知128/255保留raw并sourceMode=null、范围标志分别true/false。索引0不是空请求。与MovementSettingsProfile、推送preset、34/17-19/132等域分开，不自动组合模式或激活其他配置。写前验证/快照/停主机运动、独占至ACK，取消/超时/断线不重放/回滚/保存/读回，重连不重放，NACK不缓存兜底。modelLayout/activePreset/device/physical/persistence相关标志false，见docs/APP_PROFILE_VALUES.md。41方法源审计补充原始整数/枚举匹配与value访问器，未操作硬件、执行厂商代码或新增高级功能，全命令仍未完成。


## 0.7.19配置/工作模式验证（2026-10-17）

统一离线Node178/Web14、Python3.8/3.12各156、原生131核心+168假设备+3独立SDK、研究工具两环境各88、类型/边界/构建通过。隔离安装Node tarball178/Python wheel156通过，导入路径核对为wheel目标。41方法源码独立复现逐字节一致；0/62元数据与四工作枚举三端目录比对，原始整数/枚举value访问器及事件匹配已核对。

新增零索引/零值黄金体、配置0..5与工作四枚举、范围内未知128/范围外255保留、错域/短体/NACK、拒绝布尔/超范围/跟随标签/任意字段、参数快照/互斥、请求前后取消、超时和断连重连无重放，Web无Buffer编码。未自动写其他域/保存/回读/组合完整模式，活动预设/持久化等标志false。没有扫描、连接、移动硬件、实时UI、厂商执行或高级新增，全命令仍未完成。


## 六段40枚举引用矩阵与0D证据纠正（运行时仍0.7.19/0.3.19）

新增ronin_command_refs.py扫描40非相机枚举（39不同命令值），找到50个含引用方法、31枚举有类外字段引用，没有识别到字面量写包候选。SetOnOrOff仅枚举定义/自身引用，ordinal5、wire13，三参构造不带Class；六段无猜测的同名类定义、无枚举外引用/已识别字面量候选，payload/HG724用途仍未知。不能把枚举名当类名、类构造参数当出站实现绑定，或把0D等同参数35电机位。GetPushParams零类外引用但历史本机反馈有效，证明负面检索不能判不支持。SetAngle/AngleControl同wire0A不同协议类候选，需分开核对。

清单纠正套用的“通用方法已恢复”表述，区分枚举级证据、实现方法、HG724调用和硬件验证。字面量分析只线性语法候选，无完整CFG/异常/别名/副作用证明；1/7、保护桩/反射/动态/固件仍缺。见tools/research/COMMAND_REFERENCES.md及protocol/research/ronin-command-references.json。没有新增SDK发送、厂商执行、硬件/liveUI或高级功能，全命令门槛false。


## 2026-10-17六段命令引用矩阵验证

最终工具实际六段扫描独立复现与证据JSON逐字节一致；研究工具Python3.8/3.12各99项（新增11项）。统一离线Node178/Web14/Python156/原生131+168+3、类型/边界/构建通过。40枚举/39不同命令值、50含引用方法，31枚举有类外字段引用；0D无类外引用/已识别字面量候选/猜测同名类定义。0A两个枚举对应不同协议类候选，不合并为同一请求布局。构造器/引用/字面量候选均不当作实际发送、型号支持或全部请求体恢复。没有SDK发送扩展、硬件/liveUI/厂商执行或高级新增，运行时/安装包仍0.7.19/0.3.19，两门槛false。


## 原生角度控制静态路径（运行时仍0.7.19/0.3.19）

HG724继承链的rotate定义在基础DJIGimbalAbstraction，绝对/相对角分支均使用04:14；8字节yaw/roll/pitch signed LE、control/invalid位、float32角度乘10后截断和double时间限制0.1..25.5乘10已核对。源请求ACK但rotate调用无回调start后立即成功，不证明ACK或物理完成。justSendPauseData发送另一个stabilization START请求，接收ID通过映射，能力初始化/地址/暂停恢复未审完。

04:0A两个10字节类区分默认误差、标志和超时；AngleControl连续byte窄化不套用常见位图。六段仅DT501 UVC构造/方法两处类外直接调用，未定位HG724路径，不据此判设备不支持，UVC继续排除。48方法指纹及手写纯离线向量见tools/research/ANGLES.md与protocol/research/ronin-angles-evidence.json。没有新增SDK发送、硬件/厂商执行/liveUI或高级功能，全命令门槛仍false。


## 原生角度研究离线验证（2026-10-17）

固定六段实际扫描生成48方法指纹；新增10项编码/窄化/哈希预检，研究工具Python3.8/3.12各109通过。统一离线Node178/Web14/Python156/原生131+168+3、类型/边界/构建通过。仅研究工具/证据/文档变化，不重打运行时安装包；无硬件/liveUI/厂商执行或高级新增。


## 角度能力覆盖及暂停重载（运行时仍0.7.19/0.3.19）

29方法静态上下文审计确认HG724继承的初始化角度范围Pitch -90..90/Yaw -180..180/Roll -30..30；Handheld Roll=false被Ronin2的min/max true覆盖，非机械安全范围或动态设备读数。getGimbalIdInProtocol仅index==1映射2，其余int映射0；DataBase存储receiverID不等于-1时覆盖SendPack.receiverId，包层加密条件未审全。

justSendPauseData的无回调重载发EYE/AppState=98，SINGLE类型17/ID7，源体0100；另一个回调重载发EYE/Stabilization=96，不能合并或当04:62/04:60。无回调请求不等待业务ACK，direct BLE依赖必要性、恢复与物理效果未验证。证据protocol/research/ronin-angle-context.json及tools/research/ANGLE_CONTEXT.md。未新增SDK发送、硬件/厂商执行/liveUI、相机/视觉或高级功能，全命令门槛false。


## 角度上下文验证（2026-10-17）

固定APK/SDK实际复现29方法指纹与初始化范围覆盖。新增9项声明提取/未知写失效/分支拒绝/精确索引/哈希预检，研究工具Python3.8/3.12各118通过。统一离线Node178/Web14/Python156/原生131+168+3、类型/边界/构建通过。运行时安装包不变，无硬件或厂商执行；直接BLE依赖、恢复和物理完成仍待核对。


## stabilization状态/等待依赖静态审计（运行时仍0.7.19/0.3.19）

固定六段16方法/6直接调用方法：EYE GetPushStabilizationState=97绑定类，业务byte0的bit7开启、bit6=1且开启时未暂停、低6位原因，关闭源getter也返回paused=true。事件关闭/paused释放全部waitList，未按序号关联，不是角度到位/取消通知。等待3秒；needPause=false也发START；真实异常表16..38捕获InterruptedException到40，await中断后源标志可能保留成功，不复制为SDK取消成功。

HG724继承基础resetGimbal先调用此等待，后按平台选择DataSpecialControl或DataGimbalNewResetAndSetMode；平台分支未完整审计，不替换FE01。rotate只发送不等待；所选方法未建立恢复，不等于全App无恢复。见tools/research/STABILIZATION_DEPENDENCY.md与protocol/research/ronin-stabilization-evidence.json。没有SDK发送、相机/视觉/高级新增、硬件/liveUI/厂商执行，全部命令门槛false。


## stabilization依赖验证（2026-10-17）

实际六段复现16方法/6直接调用方法，补核PauseReason.find的OTHER回退及await真实异常表。新增9项检查，研究工具Python3.8/3.12各127通过；统一离线Node178/Web14/Python156/原生131+168+3、类型/边界/构建通过。最后补充find指纹后边界检查与两Python研究回归再次通过。运行时/安装包不变，无新增发送、硬件/厂商执行或高级功能。


## 回中源平台分支与直接App入口（运行时仍0.7.19/0.3.19）

27方法/8直接调用方法：基础resetGimbal仅PlatformType M200/M210/M210RTK选04:4C类，其余选SpecialControl；后者另按ProductType六种名字选择新旧实现，不能与HG724云台型号混用。SpecialControl业务体混合其他子系统、旧_reset保留mFlycMode且接收地址另有分支，不开放发送。

三处Ronin UI直接构造04:4C类，OTHER254+reset=true→FE01，所选方法不调用通用reset/stabilization辅助。连接/电机缓存条件、控件1000ms间隔已核对，实际HG724 UI挂载/完整可达性未验证；源字节匹配历史FE01不证明整套工作流、其他模式或物理完成。YawNoFollow0/FPV1/YawFollow2不映射PF/PTF/参数62或按轴回中。见tools/research/RESET_ROUTES.md与protocol/research/ronin-reset-routes.json。无SDK发送、相机飞行/高级新增、硬件/liveUI/厂商执行，全部命令门槛false。


## 回中分支与App入口验证（2026-10-17）

固定六段实际扫描27方法指纹/8类外直接调用方法，三个UI入口OTHER+reset true及连接/电机缓存检查已核对。新增9项检查，研究工具Python3.8/3.12各136通过；统一离线Node178/Web14/Python156/原生131+168+3、类型/边界/构建通过。运行时与安装包不变，现有FE01不替换，无硬件/厂商执行或高级新增，全命令门槛false。


## 0.7.20手柄状态被动候选 / 原生0.3.20 build23

显式ronin-2.2.2下四端handheldStickStatus/appHandheldStickStatus（Python snake别名）仅被动解码04:57：signed LE int16 X/Y、rawStateWord及bit0扳机/bit1控制、未知位/尾字节保留；不归一化或推断中心/轴映射。独立缓存、复制/不可变快照与onAppStatus kind=handheldStick，profile/断线清空，不发查询/订阅/58，不影响反馈/所有权或完成待处理请求，型号/设备/轴映射/物理标志false。23方法/2直接调用审计只见MobileHandheldController，58布尔体与ACK仅离线核对，方法名不能用来推定麦克风功能或HG724支持。无硬件/liveUI/厂商执行或高级新增，全命令未完成。见docs/APP_HANDHELD_STICK.md与tools/research/HANDHELD_STICK.md。


## 0.7.20手柄被动候选验证（2026-10-17）

固定六段实际复现23方法/2类外直接调用方法。研究工具Python3.8/3.12各144项（新增8）；统一离线Node184/Web15/Python3.8与3.12各162、原生135核心+170假设备+3独立SDK、类型/边界/构建通过。安装后的Node tarball184及类型消费、wheel162回归通过，Python导入路径核对为隔离wheel目标。

新增signed端点、独立状态位/未知高位/尾字节、短帧/ACK/加密/错端点拒绝、source gating、快照与观察者异常隔离、profile/断线清空、无58/订阅发送、通知不完成待处理参数请求、Web无Buffer验证。打包Node77文件、wheel29运行时模块、原生0.3.20/build23核对；未开启实机或实时UI，仍不能宣称完整协议或HG724手柄验证。


## 0.7.21异常/电量被动候选 / 原生0.3.21 build24

显式App来源下四端04:27/33独立abnormalStatus/batteryStatus（Python snake别名、原生app前缀）及kind事件。27有21直接getter+Roll/Pitch OR复合，不含Yaw，5字节完整已知布局；33保留原始0..255容量和尾字节，不夹取255、不并入0D02。复制/不可变快照、来源/断线清空，不影响反馈/其他缓存、所有权或待处理查询，无订阅/请求/自动控制/高级新增。36方法/2直接调用仅见MobileHandheld异常消费，无HG724布局或实机证据；型号/设备/物理标志false。见docs/APP_SOURCE_STATUS.md和tools/research/ABNORMAL_BATTERY.md，全命令门槛false。


## 0.7.21源状态候选验证（2026-10-17）

固定六段实际复现36方法/2类外直接调用方法，21字段目录逐项对比Node/Python/原生与源码证据一致。研究工具Python3.8/3.12各152（新增8）；统一离线Node190/Web16/Python两环境各168、原生139核心+172假设备+3独立SDK及类型/边界/构建通过。安装后Node190+类型消费、wheel168通过，Python路径核对为隔离wheel目标。

新增Yaw-only不算复合锁、gravity两位保留、sleep偏移4、battery255/未知尾字节、短帧/ACK/加密/错端点拒绝、来源/缓存复制及观察者异常隔离、断线/来源切换清空、无请求/订阅发送、通知不完成待处理查询、Web无Buffer检查。包内Node79文件、wheel30模块、原生0.3.21/build24核对，未运行实机或实时UI，不新增高级控制，全命令门槛false。


## 教程状态与步骤源审计（运行时仍0.7.21/0.3.21）

固定六段28方法，教程类无外部直接invoke；2B源体至少5字节，byte0步骤、offset1 signed32 LE状态，9个int0/1 getter对应bit0..8，未知23位/尾字节保留。枚举0..10，未知find回退STEP_FINISH，不能抹掉原值或作为设备完成。getStepStatus的(enumValue-2)&31使步骤0/1选择bit30/31，不推定业务用途。2C int-to-byte的一字节/ACK仅离线核对，无HG724入口/效果/恢复证明，不开放SDK发送。见tools/research/TUTORIAL.md与protocol/research/ronin-tutorial-evidence.json。没有运行时/高级新增、硬件/liveUI/厂商执行，全命令门槛false。


## 教程源审计验证（2026-10-17）

固定六段实际复现28方法/0外部直接调用。研究工具Python3.8/3.12各161项（新增9），覆盖未知回退与原值分离、signed/unsigned32视图、bit30/31回绕、9个正常步骤位、Java int低字节及哈希预检。统一离线Node190/Web16/Python168/原生139+172+3、类型/边界/构建通过。运行时与安装包仍0.7.21/0.3.21，不增加教程SDK或高级功能，不操作硬件或执行厂商代码，全命令仍未完成。


## HG724支持键声明与注册规则审计（运行时仍0.7.21/0.3.21）

固定SDK223个声明注解字段，手写KeyInfo规则模型200满足HG724支持谓词，193单字段候选唯一、7多匹配保留，不是200条BLE命令/实机能力。排除用精确Set.contains，包含用isAssignableFrom；重复包含首次保留、默认条目最后保留、getKey按HashMap首个匹配，无最具体优先证据。引用类全部有定义且无组实例化，未执行Java反射。

Rotate/ResetGimbal两条基础Action注解及12框架/动作方法指纹已核对。继承目录字段、HG724初始化覆盖、方法Map/虚调用完整路径与设备效果仍待审，不改SDK允许列表、参数行为或高级门槛。详见tools/research/KEY_SUPPORT.md和protocol/research/ronin-key-support-evidence.json；没有硬件/liveUI/厂商执行，全命令仍未完成。


## 支持键审计离线验证（2026-10-18）

固定APK/bank05实际复现223声明字段、12方法指纹和两条Action注解，重复提取JSON逐字节一致。新增14项规则/注解/哈希预检，研究工具Python3.8/3.12各175通过；统一离线Node190/Web16/Python168/原生139+172+3、类型/边界/构建通过，检查进程已结束且日志到达最后probe --help。运行时安装包仍0.7.21/0.3.21，不新增SDK发送/高级功能，无硬件/liveUI/厂商执行，全部命令门槛false。


## HG724初始化与两动作声明分派（运行时仍0.7.21/0.3.21）

固定bank05新增19方法指纹，父目录Connection/FirmwareVersion/SerialNumber三注解字段补入共226项，字符串键无重复；不是226条BLE命令。HG724 init经父类到HW初始化，component最近声明RoninBase，super链到Gimbal的GimbalKeys/getClass注册；Rotate/ResetGimbal精确签名最近声明均在基础Gimbal，无子类覆盖声明。performAction核对两Map/参数后prepend回调并Method.invoke，研究工具未执行反射。运行时实例/index、方法Map顺序/动态替换、完整参数/回调和实机仍未验证。见tools/research/REGISTRATION.md及protocol/research/ronin-registration-evidence.json；不新增SDK发送/高级功能，无硬件/liveUI/厂商执行，全命令门槛false。


## 初始化与动作声明审计验证（2026-10-18）

固定APK/bank05实际两次提取226注解字段/3继承字段/19方法指纹，JSON逐字节一致。新增11项精确签名、最近声明、循环/重复拒绝、字符串键碰撞和哈希预检，研究工具Python3.8/3.12各186通过。统一离线Node190/Web16/Python168/原生139+172+3、类型/边界/构建通过，命令进程终态0。没有运行时接口/安装包升级、SDK发送或高级新增，无硬件/liveUI/厂商执行，全命令仍未完成。


## 固件动作程序通用源审计（运行时仍0.7.21/0.3.21）

固定六段七个程序/状态类及内部类，106方法指纹/60类外直接调用；后者均bank03，未建立HG724页面/设备支持。62添加参数move/stop/yaw/pitch/roll与包内move/stop/roll/pitch/yaw不同，float32乘10 Math.round后低16位，最多10点，停止1字节且不清点。25实际最多6点、info OR不清旧位；37最多5点、mode1两字节、总时长覆盖offset2首点时长，空mode0存在源越界，不擅自修正。63混合宽度含拍摄字段，不开放发送。

38独立状态mask3与6B记录mask7分开；38/64源isChanged发送ACK，6B首字节0/1均源success、长度有符号且未完整验证、单例保留其他程序字段。离线模型严格验长并保留重复/未知记录，不复制不安全读或缓存完成语义。29项向量/边界/哈希测试；见tools/research/PROGRAMS.md、protocol/research/ronin-program-evidence.json。未新增SDK发送、相机/高级功能，无硬件/liveUI/厂商执行，全命令门槛false。


## 动作程序通用源验证（2026-10-18）

固定六段两次实际提取的106方法指纹/60直接调用方法一致，最终版补核三种整数小端转换及TimeLaps枚举。新增29项独立十六进制、负半数/窄化、点数边界、时长覆盖/空体拒绝、独立/复合状态掩码差异、未知/重复记录、截断/有符号长度与哈希预检；研究工具Python3.8/3.12各215通过。统一离线Node190/Web16/Python168/原生139+172+3、类型/边界/构建通过，进程终态0。运行时/安装包不变，没有SDK发送、相机/高级新增或硬件/liveUI/厂商执行，48条已知清单和两个完整性门槛仍未完成。


## 程序入口与产品缓存条件审计（运行时不变）

固定bank03/05的22方法/4真实AXML布局：PlatformType HG724 switch case9的isHandle返回1、getModel返回HG724，updateProduct写IsHandleDevice，UI helper读取缓存且忽略组件参数。CreateRoninNew菜单含三程序jump id，分别绑定Panorama/Track/PathDelay真实根类；实际主页面挂载/缓存仍待验证。附近HG724帮助分支是快门线帮助，不当程序证据。checkIsValuableForCreate虽有快门检查，但所选onClick不直接调用它，不虚构入口保护或宣称全局无保护。见tools/research/PROGRAM_ENTRY.md及protocol/research/ronin-program-entry-evidence.json。没有SDK发送、相机/高级新增或厂商执行/硬件/liveUI，全命令门槛false。


## 程序入口审计验证（2026-10-18）

实际两次提取22方法指纹/4布局AXML哈希及所选HG724分支，证据JSON逐字节一致。新增12项寄存器/重复/精确返回/未知父字段/跳转拒绝、XML控件和哈希预检；研究工具Python3.8/3.12各227通过。统一离线Node190/Web16/Python168/原生139+172+3、类型/边界/构建通过，进程终态0。运行时/安装包不变，无新增发送、相机/高级功能、硬件/liveUI或厂商执行，全命令及高级门槛false。


## 主页面挂载与轨迹UI工作流（运行时不变）

29方法/2挂载布局补齐MainRoninNew→入口控件→子布局RoninCreateJumpTextView id→父类菜单路由的所选静态链。子类只记录点击再super。轨迹预览ACK回调直接post PREVIEWING/IDLE，是UI状态，不当物理完成。所选状态方法无直接getCmdId/isSuccess/序号核对，可能读取共享单例保留的track字段；3秒message4重请求状态订阅，不发运动停止，1200ms是UI解锁。录制/停止分支仍含相机操作，不移植入SDK。见tools/research/TRACK_WORKFLOW.md、protocol/research/ronin-track-workflow-evidence.json。没有SDK发送、相机/高级新增、厂商执行或硬件/liveUI，全命令门槛false。


## 挂载与轨迹工作流验证（2026-10-18）

固定输入两次实际复现29方法/2挂载布局，证据JSON逐字节一致；共享常量提取增加显式选择参数后，旧22方法/4布局证据独立复现仍逐字节一致。新增12项直接调用/字符串区分、描述符、控件子类/id、默认选择不变及哈希预检，研究工具Python3.8/3.12各239通过。统一离线Node190/Web16/Python168/原生139+172+3、类型/边界/构建通过，进程终态0。运行时/安装包不变，没有SDK发送、相机/高级新增、厂商执行或硬件/liveUI，全部命令仍未完成。


## 程序基础接收路径审计（运行时不变）

固定六段、37方法/7基础程序策略：Gimbal基础枚举needCcode=true，ACK剥离外层1字节而请求通知不剥；6B block=false/mix=true可进入处理器与推送两路，38/64纯推送且源isChanged发ACK。DataBase保存按senderId数组引用，6B派生解析前先super，父层满足条件时可先post，不复制为SDK完成快照。CmdSet可反射加载CmdIdGimbalExtra；六段命名空间未找到定义，但1/7/动态未排除，基础映射不当作全App实际选择。见tools/research/PROGRAM_RECEIVE.md和protocol/research/ronin-program-receive-evidence.json。没有SDK发送/接收扩展、相机/高级新增、厂商执行或硬件/liveUI，全命令门槛false。


## 程序接收路径验证（2026-10-18）

固定输入两次实际复现37方法/7基础策略及六段扩展命名空间检索，最终证据JSON逐字节一致。新增23项外层返回码/业务成功分离、明示ccode上下文、空体/加密限制、双路与BLE ping例外、三种构造器、未解析类/哨兵拒绝及哈希预检，研究工具Python3.8/3.12各262通过。统一离线Node190/Web16/Python168/原生139+172+3、类型/边界/构建通过，进程终态0。基础表条件不提升为实际扩展/本机流量，运行时/安装包不变，无新增SDK收发、相机/高级功能、硬件/liveUI或厂商执行，全命令门槛false。


## 0.7.22程序状态被动候选 / 原生0.3.22 build25

显式App来源下四端programStatus（Python snake别名，原生appProgramStatus）及kind=program事件：38独立mask3、64 unsigned16计数、6B业务0/1与62/37/63及未知/重复记录。完整验长，源负长度高位拒绝，原值/尾字节保留。仅请求型未加密通知，ACK分开；复制/不可变独立帧快照，不保留源单例旧字段，来源/断线清空，不完成查询或改变运动所有权。不新增任何发送、订阅、自动ACK、相机/高级任务或物理完成判断。见docs/APP_PROGRAM_STATUS.md；全部命令门槛false，实机/liveUI未运行。


## 0.7.22程序候选验证（2026-10-18）

统一离线Node197/Web17/Python3.8与3.12各175、原生155核心+176假设备+3独立SDK、研究262及类型/边界/构建通过。五组JSON契约向量跨Node/Python/原生一致，新增源掩码差异、unsigned计数、未知/重复/尾字节、源失败不透明体、坏TLV/负长度拒绝、快照/观察者隔离、来源/断线清空、无ACK/订阅写入和不完成查询、Web无Buffer验证。没有实机或实时UI。

实际安装tarball后197项及TypeScript消费者通过；wheel隔离安装后175项通过，device/controller/app_commands/app_program_status导入路径已核对。Node包82文件、wheel31运行时模块逐字节匹配源码；原生ZIP内容与签名构建逐字节匹配，0.3.22/build25，未启动应用。3.12构建环境缺setuptools时改用已有3.8/setuptools75.3.4离线构建wheel，未下载依赖。所有型号/设备/物理/程序关联标志false，全命令与高级新增门槛仍false。


## 0.7.23单次程序状态请求验证（2026-10-18）

统一离线Node205/Web18/Python3.8各183、原生159核心+192假设备+3独立SDK、研究262及类型/边界/构建通过，进程终态0。Python3.12完整183项另行通过。覆盖三个固定请求体、错误profile/原始编号/订阅选项拒绝、关联ACK与通知隔离、输入快照、NACK/空ACK/加密ACK、超时/迟到/断线/取消及排队超时不迟发；原生独占/中位前导和Web blur有限查询差异保留。

实际安装Node tarball后205项及TypeScript消费者通过；wheel隔离安装后183项通过，device/controller/app_commands/app_program_request导入路径核对。所有通知新鲜度、型号布局、本机接受、程序关联及物理完成标志false。无硬件、实时UI、厂商代码执行或高级功能新增，全部命令门槛仍false。


## 0.7.24推送启停请求验证（2026-10-18）

统一离线Node213/Web19/Python3.8各191、原生167核心+217假设备+3独立SDK、研究262及类型/边界/构建通过，终态0；Python3.12完整191项另行通过。六个共享请求体跨Node/Python/原生核对，覆盖严格布尔/名称/来源/超时验证、输入复制、并发序号、ACK/通知隔离、NACK/空ACK/加密ACK、取消/超时/迟到/断线/排队不迟发和无隐式相反请求。Web保留有限查询blur差异并通过无Buffer检查。固定源程序和轨迹工作流重新实际提取，与提交的106方法/60调用及29方法/2布局证据一致。

tarball隔离安装后213项及TypeScript消费者通过；wheel隔离安装后191项通过，device/controller/app_commands/app_program_request真实导入路径核对。未扫描/连接/移动设备、运行实时UI或执行厂商代码；本机/通知流/远端订阅状态/物理效果仍未验收，全部命令和高级门槛false。


## 轨迹路点与ActualPose研究验证（2026-10-18）

最终固定APK/bank03/05实际两次复现51方法指纹、时间/参数路径和六项源DataType，证据JSON逐字节一致。新增22项边界测试；研究工具Python3.8与3.12各284通过。覆盖float32进度与分段/反向损失、pose/motor区分、signed宽度/long窄化/浮点舍入、未知/重复/缺失/截断、局部寄存器来源和两段哈希预检。统一离线Node213/Web19/Python191/原生167+217+3、类型/边界/构建通过，终态0且日志到达最终probe --help。Node/Python/macOS/Web所有源码目录与2eb2298相同，运行时/安装包保持0.7.24/0.3.24，无新增SDK收发/订阅/高级功能或硬件/liveUI/厂商执行，全命令门槛false。


## 0.7.25外设候选验证（2026-10-18）

固定源70方法/46类型/43视图两次实际提取，证据JSON逐字节一致。研究工具Python3.8与3.12各293项通过（新增9），六组共享契约覆盖完整目录、tag21碰撞、GPS整数截断、实际空记录/缺失、未知/重复/void及全长度0..127补零/符号/窄化。三端目录均逐项匹配源证据。

统一离线Node220/Web20/Python3.8共198、原生309核心+224假设备+3独立SDK、类型/边界/构建通过，终态0；Python3.12完整198另行通过。新增缓存复制/不可变/观察者隔离、来源/断线清空、CRC重组下的通知/查询/运动槽隔离、无ACK/订阅/控制写入及Web无Buffer验证。

实际安装Node tarball后220项及TypeScript消费者通过；wheel隔离安装后198项通过，device/controller/app_commands/app_peripheral导入路径核对。全部型号/设备/参考系/物理标志false，未扫描/连接/移动设备、运行实时UI或执行厂商代码；没有新增发送/高级功能，全部命令门槛false。


## 完整订阅目录验证（2026-10-18）

固定APK/bank05/DB实际两次提取24方法指纹与152命名注册，最终JSON逐字节一致；81 BaseCommand、121个DB-present命令频道对、17组别名、21资源条件键/15 Base及两处型号条件已核对。新增19项边界，研究工具Python3.8与3.12各312通过。覆盖索引非ordinal、缺失0分支/显式条件、全目录与别名位图、三命令空间、寄存器覆盖/重复/未知注册、switch数组字段和哈希预检。

统一离线Node220/Web20/Python198/原生309+224+3及类型/边界/构建通过，终态0且日志到达最后probe --help。Node/Python/macOS/Web目录与998019a相同，运行时及安装包保持0.7.25/0.3.25，不新增SDK发送/订阅管理或高级功能。资源加载顺序、组件缓存、本机路由/租期/远端停止未验收；没有硬件/liveUI/厂商代码执行，全命令门槛false。


## 订阅初始化审计（2026-10-18）

固定六段13方法审计确认元数据异步加载、逐项发布与BaseCommand构造时一次性捕获；不能推断真实调度、竞争或捕获0。独立SDK可明确选择固定DB已加载的索引分支，无需依赖App缓存；本机路由/通知/远端取消仍未验证。见[SUBSCRIPTION_INIT.md](../tools/research/SUBSCRIPTION_INIT.md)和证据protocol/research/ronin-subscription-init-evidence.json。两次实际提取JSON逐字节一致，新增7项研究测试。此研究检查点不发布新的运行时版本；已提交运行时仍0.7.25/0.3.25。单次订阅SDK正在工作树中开发，尚未交付，不计作已完成；全命令与高级门槛仍false，无硬件或厂商执行。


## 0.7.26单次命名参数订阅 / 原生0.3.26 build29

显式App来源下发送固定DB已加载/HG724静态分支的152命名键非空单次04:12请求，CENTER/id7、无ACK；报告21元数据和2型号条件键。不提供空集停止、后台刷新、反向请求或重连重放；三条中位前导及独占操作槽，不由发送成功判断远端订阅、通知新鲜度或物理效果。详见[单次参数订阅](APP_PARAMETER_SUBSCRIPTION.md)。此版本扩展此前“仅研究/工作树开发”的历史状态；实际型号/路由/通知/远端停止仍待验收，全命令及高级门槛false，无硬件/实时UI/厂商执行。


## 外设数据04:69源审计（运行时不变）

固定六段36方法、12数据类型/4来源枚举，核对tag2的控制来源及三轴signed16原值、无ACK start、空doPack和基础双路分发。仅定位跟踪界面读取两轴的一个直接调用者，无HG724或物理单位/路由证据。源旧字段保留/短包只清速度与离线独立帧视图区分；未增加SDK收发、相机/视觉或高级功能。见[EXTERNAL_DEVICE.md](../tools/research/EXTERNAL_DEVICE.md)和protocol/research/ronin-external-device-evidence.json。运行时仍0.7.26/0.3.26，全部命令及高级门槛false，无硬件/实时UI/厂商执行。


## 0.7.27外设数据被动候选 / 原生0.3.27 build30

显式App来源下externalDeviceStatus/kind=externalDevice解析04:69完整TLV，tag2保留来源及三轴signed16原值、未知/重复与尾字节；Other7与未知原值分开，不继承源单例旧值或短包清零副作用。来源/断线清空，观察者隔离；不发送/订阅/自动ACK，不完成查询或改变姿态/关节、运动所有权。见[外设数据候选SDK](APP_EXTERNAL_DEVICE_STATUS.md)。本机布局/单位/参考系均未验收，未新增相机/视觉/高级功能，无硬件/liveUI/厂商执行，全命令门槛false；此前“仅研究未接SDK”为历史状态。


## 校准08/30域与近似类绑定研究

固定六段48方法、17直接调用、9类型化声明/9枚举引用，确认04:30实际绑定SensorCalibrateStatus而非近似AutoCalibrationStatus；30状态COMPLETE0/PROCESSING1/FAIL3/OTHER9，与08响应FAIL0/SUCCESS1/PROCESSING2分开，不复用bool inProgress或system_calc表。08单字节部件及ACK业务偏移已核对，型号入口/实际扩展、路由/物理中止仍未完成。详见[校准源审计](../tools/research/SENSOR_CALIBRATION.md)及protocol/research/ronin-sensor-calibration-evidence.json。仅离线研究，运行时0.7.27/0.3.27不变，没有SDK收发、相机/视觉/高级新增或硬件/liveUI/厂商执行，完整命令门槛false。


## 0.7.28传感器校准被动候选 / 原生0.3.28 build31

显式App来源下sensorCalibrationStatus/kind=sensorCalibration解析04:30两字节源进度/状态及尾部，保留0..255原值，映射0/1/3/9并标记未知；不复用08状态或旧inProgress，不补短包默认，不由COMPLETE结束查询/运动。缓存复制/不可变、观察者隔离、来源/断线清空。见[传感器校准候选SDK](APP_SENSOR_CALIBRATION_STATUS.md)。没有查询/订阅/自动ACK/校准触发或相机/视觉/高级新增；本机/单位/请求关联与物理完成未验收，无硬件/liveUI/厂商执行，全命令门槛false。此前当前App30“未接SDK”限定为历史状态。


## 校准入口条件与HG724静态分支研究

63方法/2布局核对SystemStatus→新设置构造链、普通GYRO05/高级AUTO00的04:08及MotorEnabled缓存门槛。所选项与ModelName均HG724的显式源码情形中，普通隐藏/高级显示且旁路版本；阈值00.02.32.25严格大于、缓存/异步可见性与实际设备分开。高级ACK后60秒本地计时和百分比显示不证明固件中止/请求关联。见[校准入口研究](../tools/research/CALIBRATION_ENTRY.md)及protocol/research/ronin-calibration-entry-evidence.json。不与system_calc/index36混用，未新增SDK收发/高级功能或硬件/liveUI/厂商执行，运行时仍0.7.28/0.3.28，完整命令门槛false。


## 0.7.29接收业务解析边界 / 原生0.3.29 build32

关联App ACK、04:05反馈、04:6E调参通知和旧研究状态拒绝加密/无效flags，原始帧保持可观察；加密读取不推进参数写入，加密关节不进入定位反馈。没有新增命令、解密、协商、硬件操作或高级功能，完整命令与高级门槛仍false。契约见 docs/PLAINTEXT_BOUNDARIES.md（仓库根目录）；本版本取代此前宽松解析行为，历史版本记录保留。


0.7.29接收边界离线验收（2026-10-18）：统一检查终态0，Node247/Web24/Python3.8与3.12各222、原生669核心+250假设备生命周期+3独立SDK、研究355，类型/分层/签名构建通过。覆盖全部非零加密模式、无效flags、ACK错误分类、加密读取不推进写入、缓存隔离与定位等待下的原始假反馈；没有创建蓝牙会话、运行实时UI或执行厂商代码。未实现解密/协商或开放04:08，全部命令与高级门槛仍false。


0.7.29实际安装交付验证：Node tarball隔离安装后247项与严格TypeScript消费者通过；wheel隔离安装后222项通过，app_protocol/app_calibration/telemetry/experimental_protocol实际导入位置核对。Node99文件、wheel36模块及原生ZIP3文件逐字节匹配本次源码/签名构建，原生版本0.3.29/build32，未启动应用。没有npm发布或GitHub二进制Release。


## 校准默认包头与条件加密研究

固定六段28方法审计确认04:08新对象默认APP/id0→GIMBAL/id0、条件加密前flags40；NEEDACK.YES线上值2不是ordinal。通用发送层可按可变会话策略加密包括命令集/命令号的区间；接收事件关闭仍可能运行分类分支，不把业务Encrypt.NO当最终线上保证。见[校准传输审计](../tools/research/CALIBRATION_TRANSPORT.md)（仓库根目录）及protocol/research/ronin-calibration-transport-evidence.json。未实现/执行JNI或APK、未新增SDK收发/高级功能、没有硬件或实时UI，运行时仍0.7.29/0.3.29，完整命令门槛false。


校准传输研究验证（2026-10-18）：最终固定输入实际提取两次，28方法/1直接setter调用者（两次调用）证据JSON逐字节一致；新增13测试，研究Python3.8与3.12各368通过。统一离线Node247/Web24/Python222/原生669+250+3及类型/边界/构建通过，终态0。Node/Python/Web/macOS运行时源码与0875cdb一致，安装包保持0.7.29/0.3.29；未新增SDK发送、解密、相机/视觉/高级功能或硬件/liveUI/厂商代码执行，完整命令门槛false。


## BLE直连路由与默认策略研究

固定六段37方法核对BluetoothService→Main DJIPackManager→通用parseOne，以及监听、常规发送队列、服务切换、分片与GATT写入。Main继承needCheckEncrypt=true且构造enabledSetDataEvent=true，与DataBase共享加密管理器单例；源路由/构造策略已定位，实际会话与对端接受仍未验证。五处直接字段写入限构造，其他管理器false不套用到BLE。见[BLE路由研究](../tools/research/BLE_ROUTE.md)（仓库根目录）及protocol/research/ronin-ble-route-evidence.json。未新增SDK收发/解密/高级功能，无硬件/liveUI/厂商执行，运行时0.7.29/0.3.29及完整命令false不变。


BLE路由研究验证（2026-10-18）：最终固定输入实际提取两次，37方法/5个直接字段写入构造方法证据JSON逐字节一致。新增11项测试，研究Python3.8与3.12各379通过；统一离线Node247/Web24/Python222/原生669+250+3及类型/分层/构建通过，终态0。运行时目录与30b2a64完全一致，0.7.29/0.3.29安装包不变。没有SDK发送/解密/相机/视觉/高级新增或硬件/liveUI/厂商执行，完整命令门槛false。


## 04:08 ACK与业务域研究

固定bank05独立核对20方法，基础表ACK剥离ccode后part/status对应原始payload1/2；GIMBAL回调成功仅返回码0，与业务SUCCESS1分开。短业务体不补PROCESSING；源混合命令key仅命令集/命令/序号，不照搬到SDK严格会话/ACK/端点关联。见[校准ACK研究](../tools/research/CALIBRATION_ACK.md)（仓库根目录）及protocol/research/ronin-calibration-ack-evidence.json。没有SDK发送/解密/高级新增、硬件/liveUI或厂商执行，运行时0.7.29/0.3.29及完整命令false不变。


校准ACK研究验证（2026-10-18）：最终固定输入实际提取两次，20方法证据JSON逐字节一致。新增12项测试，研究Python3.8与3.12各391通过，覆盖全uint8部件/状态/非零返回码、短业务体、密文拒绝和key边界；统一离线Node247/Web24/Python222/原生669+250+3及类型/分层/构建通过，终态0。运行时目录与a3d4002一致，0.7.29/0.3.29安装包不变，无SDK发送/解密/高级新增或硬件/liveUI/厂商执行，全命令门槛false。


## 0.7.30部件校准候选 / 原生0.3.30 build33

显式App来源新增sendComponentCalibrationRequest(sourcePart=AUTO)，同一操作槽内停主机运动、读取35反向bit0门槛、发送04:08/00并等待严格关联ACK；禁用不自动开电机，读取与ACK共用截止时间，不重发/重放。返回码、可不完整的业务part/status和物理完成分开，不更新其他校准/传感器/姿态缓存，不提供固件中止或高级等待组合。见 docs/APP_COMPONENT_CALIBRATION.md（仓库根目录）。实际会话/设备/物理效果待验收，完整命令门槛false；未操作硬件或实时UI。


0.7.30离线验收：电机门槛固定输入实际提取两次、3方法/资源记录证据逐字节一致；新增4研究测试，Python3.8/3.12研究各395通过。统一Node255/Web25/Python3.8共230、原生949核心+263假设备生命周期+3独立SDK及严格类型/分层/签名构建通过，终态0；Python3.12完整230另行通过。七组跨端契约覆盖ACK/业务失败/未知/短体/尾部，事务覆盖禁用、坏读数、加密、busy、源切换、取消前后、迟到响应和共享预算。未操作硬件/实时UI/厂商代码，全部命令门槛仍false。


0.7.30实际安装交付验证：Node tarball隔离安装后255项与严格TypeScript消费者通过；wheel隔离安装后230项通过，app_commands/app_component_calibration/device/controller导入位置核对。Node102文件、wheel37模块、原生ZIP3文件与本次源码/签名构建逐字节一致，原生0.3.30/build33，未启动应用。没有npm发布或GitHub二进制Release。


## HG724手柄工厂与04:58键绑定研究

固定bank05核对19方法与注解，HG724条件工厂选择MobileHandheldControllerAbstraction；StickGimbalControlEnabled键支持和实际Setter注解对应04:58布尔类。方法名中的MicroPhones不定义功能，不新增麦克风/相机接口。工厂参数1是数量、普通index0，不改作接收地址；源链不证明现场反射/注册或固件效果。见[手柄绑定研究](../tools/research/HANDHELD_BINDING.md)（仓库根目录）及protocol/research/ronin-handheld-binding-evidence.json。未新增SDK收发/高级功能，无硬件/liveUI/厂商执行，运行时0.7.30/0.3.30及全命令false不变。


手柄绑定研究验证（2026-10-19）：最终固定输入实际提取两次，19方法/平台switch/Key与Setter注解证据JSON逐字节一致。新增8测试，研究Python3.8与3.12各403通过；统一离线Node255/Web25/Python230/原生949+263+3及类型/分层/构建通过，终态0。运行时目录与bac83a2完全一致，0.7.30/0.3.30安装包不变。没有SDK发送、麦克风/相机/高级新增或硬件/liveUI/厂商执行，全命令门槛false。
