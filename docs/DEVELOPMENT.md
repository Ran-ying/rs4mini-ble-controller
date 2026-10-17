# 开发背景与交接记录

## 当前边界

本项目是通过电脑 BLE 直接控制 DJI RS 4 Mini 的非官方工具。最初设想包括相机画面、
目标识别及自动拍摄；用户随后明确暂停相机集成，当前范围为稳定器连接、三轴运动与反馈。
不用 Android 桥接或蓝牙手柄。Node 是主版本，其他实现保留，按需求逐步同步。

仓库名为 `rs4mini-ble-controller`，SDK 包名仍为 `rs4mini-sdk`。仓库内没有发布 npm 包、
相机控制实现或自动追鸟功能。

## 实现演进

| 阶段 | 结果 |
|---|---|
| 原生验证 | Objective-C / CoreBluetooth 探针发现 FFF0/FFF4/FFF5 并验证速度帧 |
| 多端基础接口 | Objective-C 面板、Python Bleak、Node Noble、Web Bluetooth |
| Node 连接整理 | 每进程初始化连接，保存 UUID，直接连接失败再扫描，`close()` 清理原生运行循环 |
| Node 0.3.0 | DUML 分片/粘包重组、CRC 校验、`04:05` 姿态与关节解码 |
| Node 0.4.0 | `getAttitude()`、`getJointAngles()`、基于反馈的 `moveTo()` |
| Node 0.5.0 | `stop()` 取消位置循环、位置操作互斥、类型声明、API 文档和测试整理 |
| 本次仓库整理 | 所有源码迁入仓库、去除本机路径、交接与协议文档、诊断工具可移植化 |

## 0.6.0 跨语言基础（历史阶段）

用户要求继续完成代码并交付现有各端。Node 0.6.0 和 Web 使用共享的、与传输后端分离的
控制核心；Python 0.6.0 独立实现相同位置/反馈/取消语义并保留旧命名；原生面板 0.2.0
提供固定低速参数的目标定位、反馈显示、背压队列和停止互斥。完整功能差异见根 README。

Node 的原有纯协议和遥测导出在 Node 下保持 Buffer，在浏览器下使用 Uint8Array。
默认每个 Node 实例单独创建惰性 Noble 后端，不在未连接时初始化蓝牙。测试覆盖连接阶段
截止时间、迟到结果清理、通知监听释放、写入中停止、逐轴容差和停止阶段的操作所有权。
Python 与原生半步舍入已对齐 JavaScript 的朝正无穷方向舍入规则。

## macOS 连接经验

系统显示“已连接”不表示新的 Node 进程可直接获得旧进程的 GATT 句柄。必须执行
`connect()`，可以用已保存的 CoreBluetooth UUID 缩短扫描过程。完整示例会生成
`node/.rs4mini-device.json`；这是本机状态，禁止提交。

macOS 蓝牙权限取决于运行程序的宿主。Terminal、IDE 和桌面应用可能具有不同权限。
原始协议研究阶段 Node 宿主没有权限时，曾用原生探针抓取后由 Node 离线解码。
后续 Node 实机位置测试已成功，不应继续把 Node 无蓝牙权限当作固定结论。

`stop()` / `disconnect()` / `close()` 是不同生命周期动作；命令行 `finally` 使用 `close()`，
否则 Noble 的原生运行循环可能使程序完成后仍不退出。

## 反馈解码经验

先静止采样，再分别 Pan、Tilt、Roll 往返，最后转动手柄，比较姿态和关节字段。
这样可以区分平台方向、机械角与云台补偿。具体字节映射在 [PROTOCOL.md](PROTOCOL.md)。
姿态 Pitch 在测试姿态中接近 ±180° 是正常观测，不能把它当成 Joint Pitch 的相同目标。
Roll 动作可能伴随固件补偿或平台姿态变化，用户已决定保留补偿行为。

## 位置控制经验

为避免未验证绝对角命令造成大幅跳转，`moveTo()` 采用已验证速度帧加约 1 Hz 关节反馈。
初始先做 Pan 5° 往返，再按用户要求扩展到 Pan 20°，然后 Tilt/Roll 12°。
这些是单轴、低速、容差 1° 的测试；没有完整验证多轴轨迹、极限位置或高频跟踪。

调试时先确认坐标与正负号，再调节 gain、minSpeed 和 maxSpeed。速度满量程换算仅为经验值，
不要把 `30°/s` 当成硬件最大速度。`moveTo()` 目标限制也不等同机械限位或防碰撞逻辑。

## 开发与验证边界

此前登记的代码边界已经落实为实现与离线回归，包括位置清理互斥、多轴逐轴容差、总超时、
连接各阶段截止时间、回调隔离、限时运动取消和重连监听清理。统一检查入口为
`sh tools/check-offline.sh`。此次代码修改期间不连接硬件。

0.6.0 的物理运动、OS 蓝牙权限与回调、浏览器生命周期和新原生 UI 的硬件结果尚未验证，
需用户回家后按 `HARDWARE_CHECKLIST.md` 执行。历史实测不为新取消/队列行为背书。
不新增未经本设备验证的绝对角协议或单轴回中，不自动恢复断线前运动。

## 本次迁移说明

- 迁入 Node/Python/macOS/Web 全部可维护源码与文档，保留 Node 锁文件。
- 保留原生 BLE 探针源码，移除其无参数时自动查询、写开发者绝对路径的行为；现在默认仅扫描。
- 未带入第三方研究仓库、固件文件、原始设备日志、依赖目录、生成的 `.app` 或可执行文件。
- 原目录后来出现的 `node/examples/test.js` 是个人无限循环运动脚本，未作为公共示例迁入；
  原文件保留在原位置。公共演示为 `full-demo.js` 和 `position-demo.js`。
- 日志与设备标识不会进入 Git；验证证据由 [VALIDATION.md](VALIDATION.md) 中的匿名数值保留。
- 所有安装、构建、测试命令按仓库相对目录执行，不依赖聊天工作目录。

## 当前 0.7.0 检查点与 GitHub 交接

Node/Python/Web 0.7.0、原生面板 0.3.0 已完成本轮扩展的代码和离线交付；
具体能力、测试、差异和未完成项目统一以 [项目状态](PROJECT_STATUS.md) 为入口。
用户于 2026-10-15 明确要求将源码与相关信息提交到 GitHub。仓库保存源码、
协议证据、验证记录和后续清单；本机设备缓存、抓包、依赖、研究下载及生成应用继续忽略。
完整非相机目标和统一实机验收仍未完成，不因源码提交而改变这一状态。

## 0.7.1 设备 SDK 与高级封装

按用户要求分离设备访问与已有高级运动；应用保持唯一高级入口，基础操作也从上层对象调用。
设备层与上层通过继承和共享操作协调器协作，保持单连接、单写入队列、统一取消/停止。
Node/Web、Python 与原生已分别拆分；完整模块映射见 `ARCHITECTURE.md`。
底层命令尚未全部解析/封装/验收，新增高级功能暂停，依据为 `SDK_COMMANDS.md` 与机器命令清单。


0.7.3 将已恢复 HG724 参数静态链接入四端设备 SDK；接口和并发差异见 APP_COMMANDS.md。ronin_command_audit.py 可重现方法指纹。源码证据与硬件证据分开，继续其余底层命令，高级门槛仍 false。


0.7.4 继续封装继承源码中的八个布尔setter，合并为两组命名SDK事务，复用已有连接和操作槽；不是新增八个固件命令。见 APP_SETTINGS.md。其余命令和全量硬件验收仍未完成。


0.7.5 检查继承覆盖后封装了当前型号自动调参请求与校准状态，避免沿用Ronin2父类路径或错误等待ACK。没有高级程序等待/物理完成承诺，见 APP_CALIBRATION.md。


## 0.7.6 命名电机参数

0.7.6 新增十二个命名电机数值的四端SDK、类型和离线回归；复现工具 ronin_motor_trace.py 固定APK/恢复视图哈希并核对26个方法指纹、INT08U分支和低字节编码。参数范围仅是源码校验，不是机械安全范围。详见 [APP_MOTOR_TUNING.md](APP_MOTOR_TUNING.md)。


## 0.7.7 平衡测试SDK

四端封装0F/10命名平衡测试启动64与状态/三轴结果，零结果保留null，取消不发未证实的中止。Node102/Web14/Python两环境各80/native72+94+3/research42，类型/边界/构建通过。没有硬件、UI或高级新增；实机效果与全部命令仍未验收。详见 [APP_BALANCE_TEST.md](APP_BALANCE_TEST.md)。


## 0.7.8 system_calc自动校准

四端新增独立的普通0F/10/index36固定启动1和状态读取，与6A/6E自动调参分开。读取状态2/3不受写入范围0..1限制，未知值保留raw/null；ACK/报告不代表本次物理完成，取消不保证固件中止，无虚构写零停止。Node108/Web14/Python各86/native75+101+3/research45，类型/边界/构建通过。尚无水平校准身份或本机验收，未操作硬件/UI或新增高级任务。详见 [APP_SYSTEM_CALIBRATION.md](APP_SYSTEM_CALIBRATION.md)。


## 多段代码恢复续报

严格恢复固定APK6段49,542条原code_item，原business05哈希保持一致；2段仍缺可靠元数据，未恢复。新增40个模式键UI调用方指纹，可继续核对两位字段打包与型号分支。研究48项在Python3.8/3.12通过，实际独立目录复现一致；无SDK发送扩大、硬件/UI或厂商代码执行。运行时仍0.7.8/0.3.8，全协议/高级门槛false。见 [CODE_BANKS.md](../tools/research/CODE_BANKS.md)。


## 0.7.9 跟随/RC按轴档位

六组参数档位已同步四端，Pitch/Roll/Yaw字段为bits2..3/4..5/6..7，custom/low/middle/high为0/1/2/3；先读后改写，保留其他轴和未知低两位，共用操作槽和总截止时间。Node113/Web14/Python各91/native79+107+3/research49，类型/边界/构建通过；无硬件/UI/高级新增，PF/PTF和custom数值未因此完成。详见 [APP_FOLLOW_MODES.md](APP_FOLLOW_MODES.md)。


## 数值参数与输入源分支续报

18项普通跟随/RC数值已核对有效继承、命名映射、缺省读取模型及INT08U/INT16U两条单项/数组打包分支；另6项独立配置在App与输入源2同包写入，不能按名称相似自动替换。42方法指纹实际固定APK复现一致；研究53项在Python3.8/3.12通过，无新增SDK发送或硬件/UI操作。运行时仍0.7.9/0.3.9，全协议和高级门槛false。见 [NUMERIC_PARAMS.md](../tools/research/NUMERIC_PARAMS.md)。


## 0.7.10 普通数值SDK

18项普通跟随/RC数值已同步四端，1/2字节小端与无符号异常原值按上下文解码，单项写入独占到ACK、取消无重放。不自动切档位/预设/输入源，activePresetVerified:false，独立配置和实机效果仍待完成。Node120/Web14/Python各97/native83+113+3/research53，类型/边界/构建通过，三端目录逐项匹配源码。无硬件/UI或高级新增。详见 [APP_NUMERIC_TUNING.md](APP_NUMERIC_TUNING.md)。


0.7.11增加独立配置的六项命名数值与显式输入源2同包事务，04:0F写/04:10按外部宽度读；读取不切源，未知源和值保留。源码条件关联至Model.HG724，尚无设备验证。见 [APP_STANDALONE_TUNING.md](APP_STANDALONE_TUNING.md)。这不完成PF/PTF/FPV预设、固件原生程序或全部命令，完整性和高级新增门槛仍false。


2026-10-17预设研究新增26个方法指纹：UserProfile/table_choice、MovementSettingsProfile和GimbalWorkMode分别核对；HG724条件新模式列表为FPV/Custom/3D Roll 360，不能照搬旧PF/PTF位置。业务getPresetID偏移2尚未证明原始BLE偏移，SDK不解码为活动预设。见 [PROFILES.md](../tools/research/PROFILES.md)。运行时仍0.7.11/0.3.11，未新增接口或操作硬件，全命令门槛false。


后续订阅审计确认04:12为CENTER/id7无ACK、最高频道号+位图及本地引用计数刷新；本地停发不能当远端取消。未加密请求型04:24的源payload偏移2已追通，但不代表本机活动预设或04:10参数订阅。见 [SUBSCRIPTIONS.md](../tools/research/SUBSCRIPTIONS.md)。本批不新增SDK发送/解码接口，运行时与全命令门槛不变。


0.7.12将04:24的17个已审计getter接入四端被动缓存，完整已知布局至少74字节，保留未知原值、限定未加密请求型和端点，不触发订阅、主动查询或预设激活。通用源布局不是本机验证，更多字段和全部协议仍未完成。见 [APP_USER_PARAMETERS.md](APP_USER_PARAMETERS.md)。


后续微调/手柄/重置审计固定42方法：微调轴值0/2/4，手柄8字节与FF默认/只重置6项，HG724平台重置010001。保存空体类在两段未见直接调用者，不代表全App否定。详见 [FINE_HANDLE_RESET.md](../tools/research/FINE_HANDLE_RESET.md)。本批未新增SDK发送或实机证据，运行时不变，全命令门槛false。


0.7.13在显式App来源下增加04:36手柄只读查询和8字段原值/bit0解析，不写35/11/13或填04:24缓存；继承路径有源码证据，实际型号布局/效果未验证。见 [APP_HANDLE_SETTINGS.md](APP_HANDLE_SETTINGS.md)。全命令及高级门槛仍false。


0.7.14的sendFineTuneRequest是设备04:07源请求封装，Pitch/Roll的float32参数编码、ACK与主机取消分别处理；不计作高级组合或实际角度完成。暂停稳定/本机效果及其余命令仍未验收。见 [APP_FINE_TUNE.md](APP_FINE_TUNE.md)。


## 0.7.15手柄单字段请求 / 原生0.3.15 build18

四端设备SDK的sendHandleSettingRequest（Python snake别名）显式App来源下仅接受dualChannelMode/tiltDirection/panDirection单字段及整数0/1，8字节35体未指定字节为源默认FF。新对象/独立体，不全量读改写、不新增相机字段。参数停止前验证/快照，复用连接/队列/操作所有权至关联ACK；取消/超时无重放或回滚，NACK直接失败、不缓存兜底成功、不自动回读。结果unspecifiedByteSemanticsVerified/readbackVerified/persistenceVerified及既有设备/物理标志均false。FF实际含义、模式/方向效果、持久化待本机验收。见docs/APP_HANDLE_WRITE.md；没有高级新增或硬件操作，全部命令门槛仍false。


## 0.7.16恢复设置请求 / 原生0.3.16 build19

四端sendFactorySettingsResetRequest（Python snake别名）需显式App来源和sourcePlatform HG724，固定04:13/010001；不是类型枚举103或其他平台空体。停止前验证/快照，复用连接/队列/操作槽至关联ACK。取消/超时/断线不重发、不自动保存/回读/回滚，重连不重放。ACK不证明恢复范围、持久化、重启或物理完成，相关标志false，不自动清零/改写反馈或参数。恢复范围也未证明仅非相机字段。68方法审计新增成功/失败回调，未解析完成。见docs/APP_FACTORY_RESET.md。没有硬件/liveUI/厂商执行或高级新增；全部命令仍未完成。


## 0.7.17轴模式34读写 / 原生0.3.17 build20

四端getAxisMode/sendAxisModeRequest（Python snake别名）在显式App来源下封装34/size1。四个源枚举写0/8/16/24，读(raw>>3)&3，保留raw/unknownBits=raw&0xe7及headerByte，modelLayout/activePreset/device/physical标志false。HG724 UI只定位ThreeAxis及ThreeDRoll360，不宣称全部四种固件支持。源setter整字节写，不擅自RMW或保留其他位，otherBitsPreservationVerified/persistenceVerified=false。参数快照、写先停主机运动并独占至ACK，取消/超时/断线无重放/回滚，NACK不缓存兜底；不自动写132、17/18/19、35或激活预设，不是完整跟随模式。Node/Python有限读并发与原生读占槽差异保留。见docs/APP_AXIS_MODE.md；未操作硬件/执行厂商代码/新增高级任务，全命令未完成。


## 0.7.18普通跟随轴开关 / 原生0.3.18 build21

四端getSmoothTrackAxes/sendSmoothTrackAxesRequest（Python snake别名）显式App来源下封装17/18/19、size1，默认读三轴/可过滤单轴，写非空命名布尔子集，一条0F按yaw/pitch/roll排序，未指定字段省略。源App直接参数数组路径已确认，本次未定位逐轴SDK setter；不将其不存在或本机支持当结论。读raw0/1→enabled false/true，其他→null，保留raw/header、sourceEnabled=(raw==1)与withinSourceRange，不按bit0或错误码丢值。参数快照/写先停/独占至ACK，取消/超时/断线无重放/回滚，重连不恢复请求；不自动写132/34/35/预设/输入源/保存，不是完整模式。atomicApplication/activePreset/modelLayout/device/physical/persistence相关标志false。见docs/APP_SMOOTH_TRACK.md；没有高级新增、硬件/厂商执行，全命令仍未完成。


## 0.7.19配置0与工作模式62 / 原生0.3.19 build22

四端getUserProfile/sendUserProfileRequest、getWorkMode/sendWorkModeRequest（Python snake别名）显式App来源下独立读写0/62、size1。配置源范围0..5，源UI名仅0/1/2=M1/M2/M3，其他不推断运动预设；工作写仅精确Free/Flower/Fpv/Center四枚举，读取未知128/255保留raw并sourceMode=null、范围标志分别true/false。索引0不是空请求。与MovementSettingsProfile、推送preset、34/17-19/132等域分开，不自动组合模式或激活其他配置。写前验证/快照/停主机运动、独占至ACK，取消/超时/断线不重放/回滚/保存/读回，重连不重放，NACK不缓存兜底。modelLayout/activePreset/device/physical/persistence相关标志false，见docs/APP_PROFILE_VALUES.md。41方法源审计补充原始整数/枚举匹配与value访问器，未操作硬件、执行厂商代码或新增高级功能，全命令仍未完成。


最新[原生角度控制研究](../tools/research/ANGLES.md)已区分04:0A两种布局与HG724继承rotate的04:14路径；能力/地址/暂停及物理完成仍待核对，未新增当前App角度发送接口。


后续[角度能力与包上下文研究](../tools/research/ANGLE_CONTEXT.md)核对初始化覆盖、接收ID传递及EYE两个不同重载；本机地址、依赖适用性/恢复与物理完成仍未验收，没有新增发送。


[暂停状态与等待依赖审计](../tools/research/STABILIZATION_DEPENDENCY.md)区分源stabilization状态、3秒等待与真实云台停止/到位；关闭也返回paused、等待不按请求序号关联，未新增运行时功能或声明本机支持。


[回中平台分支与App入口研究](../tools/research/RESET_ROUTES.md)已区分通用SpecialControl流程和三处直接FE01源分支；现有实测回中保持不变，未开放其他模式或混合控制发送。


0.7.20新增[手柄状态被动候选](APP_HANDHELD_STICK.md)，仅显式App来源、无58发送/订阅，真实57布局、单位与轴映射等待本机验收；未新增高级功能。
