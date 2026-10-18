# RS 4 Mini BLE 协议记录

这是本项目的实现记录，不是 DJI 官方协议。偏移均从 payload 的第一个字节开始计算。

## BLE 和 DUML

| 项目 | 值 |
|---|---|
| Service | `FFF0` |
| Notify | `FFF4` |
| Write without response | `FFF5` |
| APP / GIMBAL 地址 | `02 / 04` |
| 发送切片大小 | 20 字节 |
| 默认速度发送频率 | 15 Hz |
| 已观察到的 `04:05` 反馈频率 | 约 1 Hz |

DUML 编码结构：

| 帧偏移 | 内容 |
|---:|---|
| 0 | 起始字节 `55` |
| 1–2 | 10-bit 总长度；byte 2 同时包含 `04` 版本位 |
| 3 | 前三字节的 CRC8 |
| 4–5 | sender / receiver |
| 6–7 | sequence，uint16 LE |
| 8 | flags |
| 9–10 | command set / command id |
| 11… | payload |
| 最后两字节 | 帧末尾之前所有字节的 CRC16，uint16 LE |

CRC8 初值 `77`，反射多项式 `8C`；CRC16 初值 `3692`，反射多项式 `8408`。
`node/src/protocol.js` 是编码参考，`node/src/telemetry.js` 负责接收重组及校验。
BLE 通知可能分片或粘包，不能把每个通知直接当作完整 DUML 帧。

## 速度和回中

速度 `04:01` payload 长 9 字节：

```text
int16 LE tilt
int16 LE roll
int16 LE pan
int16 LE zero = 0
uint8 source = 02
```

每轴 RC 值是 `1024 + round(clamp(input,-1,1) * 660)`。连续发送保持速度，
停止时发送三个全零输入对应的中位帧。sequence=`0100` 的停止黄金向量：

```text
551604fc020400010004010004000400040000027705
```

三轴回中 `04:4C`：payload=`FE 01`，flags=`40`。没有验证可单独指定轴的回中命令。

## `04:05` 姿态与关节角

原始测试中为 49 字节 payload，字段如下：

| 数据 | 偏移 | 编码 |
|---|---:|---|
| Attitude Pitch | 0 | int16 LE / 10，度 |
| Attitude Roll | 2 | int16 LE / 10，度 |
| Attitude Yaw | 4 | int16 LE / 10，度 |
| modeFlags | 6 | uint8；位语义未完整验证 |
| rollAdjust | 7 | int8；不用于位置闭环 |
| yawAngle 辅助字段 | 8 | int16 LE / 10；不用于位置闭环 |
| limitFlags / stateFlags | 10 / 11 | uint8；位语义未完整验证 |
| Joint Yaw | 16 | int16 LE / 100，度 |
| Joint Pitch | 20 | int16 LE / 10，度 |
| Joint Roll | 22 | int16 LE / 10，度 |
| 疑似四元数 | 24 / 28 / 32 / 36 | 四个 float32 LE，分量顺序未验证 |

姿态角会在 ±180° 环绕，不能直接用未处理环绕的数值差计算运动量。
关节角和平台姿态是不同坐标量。反馈中的零点不代表当前安装姿态的视觉水平或构图中心。
已实测的 Joint 角误差到速度指令方向：Pan `+`、Tilt `-`、Roll `+`。

## 查询和未采用命令

- `04:02` 空 payload 位置查询：在测试设备上未观察到有效响应。
- `04:1E` 空 payload degree-info 请求：有 `00` 成功响应，但未观察到反馈频率提高。
- 外部协议研究涉及 `04:0A` 和 `04:14` 绝对角命令；RS 4 Mini 的坐标语义和
  兼容性尚未实机验证。本 SDK 的 `moveTo()` 不使用它们。
- 官方 DJI R SDK 中的 `AA` CAN 帧协议与这里的 `55` BLE DUML 不相同，不能直接混用。

## 研究入口

这些是开发过程中查阅过的外部资料入口，不代表它们为本项目 RS 4 Mini 映射背书：

- [DJI RS SDK](https://www.dji.com/rs-sdk)
- [lib-osmo-ble](https://github.com/yigitkonur/lib-osmo-ble)
- [dji-firmware-tools gimbal dissector](https://github.com/o-gs/dji-firmware-tools/blob/master/comm_dissector/wireshark/dji-dumlv1-gimbal.lua)

以后变更协议字段时，优先提供本设备的分轴运动或离线合成帧证据，并在这里记录验证范围。

## 非相机扩展的研究配置（尚未验证 RS 4 Mini）

本轮只研究和运行离线测试，没有对稳定器发出新增命令。

| 配置/来源 | 本项目采用的内容 | 验证边界 |
|---|---|---|
| [RS 3 原始研究](https://github.com/jdesbonnet/dji_rs3_control/blob/689884f2249e721c5b65c9c74804caddc1e7a68c/rs3_ble_protocol_spec.md) | `04:14` Pan/Roll/Tilt 十分之一度、无效轴掩码；`04:0C` 同次序原生速率；`04:0F` 休眠/唤醒 | 原作者只实测部分 Pan 行为；其他轴、控制位、末参数单位与本型号均需验证 |
| [RS 3 Mini 原始实现](https://github.com/b-rutledge-code/rs3mini-bridge/blob/b64315754bb47be76d862ae8860764267215a7cf/lib/session-setup.js) | `04:0F` 型号独立的休眠字节 | 与 RS 3 字节不同，因此必须显式选择配置 |
| [RS 3 Mini 状态实现](https://github.com/b-rutledge-code/rs3mini-bridge/blob/b64315754bb47be76d862ae8860764267215a7cf/lib/telemetry.js) | `0D:02` 的原始字段和候选百分比，`04:66` TLV | 本项目严格检查端点/长度；保留原始量，不用该布局覆盖 RS 4 Mini 关节角 |

`experimental.absolute()` 按省略轴设置无效位；`parameterByte` 必须由调用方显式提供，
不把未确认的末参数解释成秒。`observeMs` 只是本地观察时长，不是固件运动时间或到位判断。
`experimental.rateFor()` 的清理先尝试 `04:0C` 零速/释放，再发送普通中位帧。
这些写入均不能证明固件会执行或能够中断自身的动作。

`experimental.query()` 只开放 version=`00:01`、position=`04:02`、
controlStatus=`04:0B`、type=`04:1C`，匹配同连接、sequence、`04→02`、命令及响应位。
它不开放任意命令、固件更新或校准触发；超时表示没有观察到关联响应，不能直接判定固件不支持。

研究还发现校准 `04:08` 在 RS 3 上可能自主运动，且额外流量会干扰校准；
本轮只解析候选进度 `04:30`，尚未开放触发接口。真正单轴回中、跟随模式参数、
完整校准与电机调参、原生轨迹/全景程序仍需补充协议依据和受控验证。
Osmo 示例的角度次序与这些 RS 资料冲突，不能直接移植。

四元数接口只提供显式分量顺序下的标准右手内禀 ZYX 数学转换，
结果带 `deviceConventionVerified:false`；没有自动识别 RS 4 Mini 坐标约定。

## 0.7.1 设备模块审计

现有编解码/发送已从主机运动算法中独立；详见 `ARCHITECTURE.md`。
`requestDegreeInfo()` 补齐 04:1E 空负载请求和关联原始响应封装；没有对硬件执行，不解释新的响应字段或宣称增频。
所有已知命令和未知缺口在 `../protocol/COMMANDS.json` 与 `SDK_COMMANDS.md` 中逐项记录。
这份清单不构成完整固件 BLE 指令表，未完成本机语义和枚举证明前不进入新增高级功能阶段。

## 0.7.2 被动用户参数候选解析

依据 [o-gs 原始 DUML 解码器](https://github.com/o-gs/dji-firmware-tools/blob/master/comm_dissector/wireshark/dji-dumlv1-gimbal.lua)
（本轮检查的文件 Git blob：`544f758ee1890c0be55687f8db52c970241d3736`），以及已登记 RS 3 来源的
`04:10 payload=12` / 响应 `00120100` 样本，显式研究配置支持以下候选格式：

- 仅 `04→02`、command-set=04、响应位 80 的消息进入新解析分支。
- 04:10：首字节为原始返回码；后续正索引项为 index / size / raw bytes，宽度严格限定 1/2/4/8。
  旧格式中的负 int8 项作为逐项 errorCode 保留。数组保留重复索引；截断、零宽度或未知宽度拒绝。
- 04:0F：仅一字节响应返回原始 statusCode。既有研究 sleep 布局不受影响。
- 新结果为 `user-parameters` / `user-parameter-ack`，附 `layoutSource:'legacy-duml'` 与
  `deviceVerified:false`。不会根据资源表自动命名参数、解释有符号/浮点数或判定本机兼容。

该来源是早期其他产品格式，不是 RS 4 Mini 字段验证。显式研究配置默认不启用；本轮不增加查询或写入接口。
官方 Ronin APK 的可读枚举和参数资源作为独立事实保存，不能替代协议布局与本机证据。


## 后续 MSDK 交叉证据

官方 provided 4.18 JAR 的不可达字节码尾部提供旧版 04:4C、04:32、04:35/36 候选结构，
只供离线核对，详见 [研究说明](../tools/research/MSDK_V4.md)。它没有恢复当前 Ronin App 的有效打包方法。
旧回中枚举与本机 FE01 三轴回中存在语义差异；接收包可能先剥离返回码，业务方法偏移不能直接复制到 BLE 解码器。
不据此改变现有研究配置或本机反馈映射，没有新增发送接口。


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


## 0.7.3 当前 App 参数事务

显式来源 SDK 的04:0F/04:10返回码与高索引解码、外部宽度上下文及来源边界见 [APP_COMMANDS.md](APP_COMMANDS.md)。Ccode.OK=0；返回码与业务索引分离，第二头字节不解释为宽度。不是新硬件证据。


0.7.4 补齐两组命名位字段的寄存器读写事务：132自定义跟随、35电机标志。掩码、极性、来源与未验收边界见 [APP_SETTINGS.md](APP_SETTINGS.md)。未知位不覆盖，不从位字段推断PF/PTF或物理效果。


0.7.5 已沿HG702覆盖路径确认04:6A为00 01 bool且不请求ACK，04:6E查询/通知业务体为记录。返回码与记录首tag不能混用，发送不代表完成；完整来源、长度边界和状态语义见 [APP_CALIBRATION.md](APP_CALIBRATION.md)。


## 0.7.6 命名电机参数

0.7.6 命名电机数值使用独立04:31/32命名空间，索引0..11、size1、INT08U。04:32按请求上下文解码，第二头字节仍原样保留；04:31 ACK不代表参数已物理生效。详见 [APP_MOTOR_TUNING.md](APP_MOTOR_TUNING.md)。


## 0.7.7 平衡测试SDK

四端封装0F/10命名平衡测试启动64与状态/三轴结果，零结果保留null，取消不发未证实的中止。Node102/Web14/Python两环境各80/native72+94+3/research42，类型/边界/构建通过。没有硬件、UI或高级新增；实机效果与全部命令仍未验收。详见 [APP_BALANCE_TEST.md](APP_BALANCE_TEST.md)。


## 0.7.8 system_calc自动校准

四端新增独立的普通0F/10/index36固定启动1和状态读取，与6A/6E自动调参分开。读取状态2/3不受写入范围0..1限制，未知值保留raw/null；ACK/报告不代表本次物理完成，取消不保证固件中止，无虚构写零停止。Node108/Web14/Python各86/native75+101+3/research45，类型/边界/构建通过。尚无水平校准身份或本机验收，未操作硬件/UI或新增高级任务。详见 [APP_SYSTEM_CALIBRATION.md](APP_SYSTEM_CALIBRATION.md)。


## 0.7.9 跟随/RC按轴档位

六组参数档位已同步四端，Pitch/Roll/Yaw字段为bits2..3/4..5/6..7，custom/low/middle/high为0/1/2/3；先读后改写，保留其他轴和未知低两位，共用操作槽和总截止时间。Node113/Web14/Python各91/native79+107+3/research49，类型/边界/构建通过；无硬件/UI/高级新增，PF/PTF和custom数值未因此完成。详见 [APP_FOLLOW_MODES.md](APP_FOLLOW_MODES.md)。


## 数值参数与输入源分支续报

18项普通跟随/RC数值已核对有效继承、命名映射、缺省读取模型及INT08U/INT16U两条单项/数组打包分支；另6项独立配置在App与输入源2同包写入，不能按名称相似自动替换。42方法指纹实际固定APK复现一致；研究53项在Python3.8/3.12通过，无新增SDK发送或硬件/UI操作。运行时仍0.7.9/0.3.9，全协议和高级门槛false。见 [NUMERIC_PARAMS.md](../tools/research/NUMERIC_PARAMS.md)。


## 0.7.10 普通数值SDK

18项普通跟随/RC数值已同步四端，1/2字节小端与无符号异常原值按上下文解码，单项写入独占到ACK、取消无重放。不自动切档位/预设/输入源，activePresetVerified:false，独立配置和实机效果仍待完成。Node120/Web14/Python各97/native83+113+3/research53，类型/边界/构建通过，三端目录逐项匹配源码。无硬件/UI或高级新增。详见 [APP_NUMERIC_TUNING.md](APP_NUMERIC_TUNING.md)。


0.7.11增加独立配置的六项命名数值与显式输入源2同包事务，04:0F写/04:10按外部宽度读；读取不切源，未知源和值保留。源码条件关联至Model.HG724，尚无设备验证。见 [APP_STANDALONE_TUNING.md](APP_STANDALONE_TUNING.md)。这不完成PF/PTF/FPV预设、固件原生程序或全部命令，完整性和高级新增门槛仍false。


0.7.12将04:24的17个已审计getter接入四端被动缓存，完整已知布局至少74字节，保留未知原值、限定未加密请求型和端点，不触发订阅、主动查询或预设激活。通用源布局不是本机验证，更多字段和全部协议仍未完成。见 [APP_USER_PARAMETERS.md](APP_USER_PARAMETERS.md)。


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


0.7.21新增[异常与电量被动候选](APP_SOURCE_STATUS.md)，显式App来源、原始位/255保留，不触发请求或自动控制；本机布局与通知仍未验收。


[教程命令源审计](../tools/research/TUTORIAL.md)记录未知步骤回退与32位移位边界；未定位HG724业务入口，不新增教程发送或以教程标志判定运动完成。


[HG724支持键规则研究](../tools/research/KEY_SUPPORT.md)区分声明支持谓词、缓存动作注册与原生BLE命令；保留多匹配歧义，不据键数量声明协议完整或新增发送。


[HG724初始化与动作声明分派](../tools/research/REGISTRATION.md)补齐继承目录及两个动作的静态声明链，仍非运行时注册或本机验收；不改变SDK发送与高级门槛。


[固件动作程序通用源审计](../tools/research/PROGRAMS.md)核对62/25/37/63请求与38/64/6B状态差异；仅静态业务体证据，尚无HG724完整路径或SDK新增发送，全命令门槛false。


[程序菜单与HG724条件分类](../tools/research/PROGRAM_ENTRY.md)补齐产品缓存/布局声明链，区分快门线帮助与检查函数可达性；尚未证明完整型号工作流，不新增发送或高级功能。


[主页面挂载与轨迹UI工作流](../tools/research/TRACK_WORKFLOW.md)补齐静态挂载链，区分ACK后的界面状态、重订阅和物理停止；仍未开放程序SDK或高级功能。


[程序基础接收路径](../tools/research/PROGRAM_RECEIVE.md)区分ACK返回码与业务首字节、6B双路分派及扩展命令表边界；仅静态研究，不新增SDK发送或高级功能。


0.7.22新增[程序状态被动候选](APP_PROGRAM_STATUS.md)：显式App来源下38/64/6B独立帧快照，未知/重复记录保留，无查询/订阅/自动ACK，不等于物理完成；完整命令仍未验收。


0.7.23新增[单次程序状态请求](APP_PROGRAM_REQUEST.md)：显式App来源、固定type2与三个命名程序，仅关联ACK、业务体不透明；不承诺新通知，不增加连续订阅或动作执行，本机未验收。


0.7.24新增[程序状态推送启停请求](APP_PROGRAM_SUBSCRIPTION.md)：显式program与布尔enabled，固定type0/1及关联ACK；不证明远端订阅状态、不自动维护或恢复订阅，不发送动作程序命令。本机仍未验收。


新增[轨迹路点与ActualPose审计](../tools/research/TRACK_POINTS.md)：UI秒数分段、首点/Roll规则及04:66缓存来源已核对，不能把原生轨迹角度直接当作现有机械关节角。仅研究，无SDK发送或硬件操作，运行时仍0.7.24/0.3.24，全命令门槛false。


0.7.25新增[外设状态源候选](APP_PERIPHERAL_STATUS.md)：46源类型/43 getter视图、保留tag21碰撞和GPS整数截断；不改现有姿态/关节，不自动ACK/订阅或控制，本机未验收。


新增[完整订阅键与初始化条件审计](../tools/research/SUBSCRIPTION_CATALOG.md)：152个注册键分开记录显式索引、21个元数据条件键与2个型号条件；不将缺失0或资源预期索引自动变成SDK发送表。仅离线研究，运行时仍0.7.25/0.3.25，全命令门槛false。


0.7.26新增[单次命名参数订阅请求](APP_PARAMETER_SUBSCRIPTION.md)：固定DB已加载/HG724静态分支、152命名键、CENTER/id7无ACK，仅一次请求。没有空集停止、后台刷新或重连重放；本机路由/通知/远端状态仍未验收，不改变完整命令及高级门槛。


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


## 校准默认包头与条件加密研究

固定六段28方法审计确认04:08新对象默认APP/id0→GIMBAL/id0、条件加密前flags40；NEEDACK.YES线上值2不是ordinal。通用发送层可按可变会话策略加密包括命令集/命令号的区间；接收事件关闭仍可能运行分类分支，不把业务Encrypt.NO当最终线上保证。见[校准传输审计](../tools/research/CALIBRATION_TRANSPORT.md)（仓库根目录）及protocol/research/ronin-calibration-transport-evidence.json。未实现/执行JNI或APK、未新增SDK收发/高级功能、没有硬件或实时UI，运行时仍0.7.29/0.3.29，完整命令门槛false。


## BLE直连路由与默认策略研究

固定六段37方法核对BluetoothService→Main DJIPackManager→通用parseOne，以及监听、常规发送队列、服务切换、分片与GATT写入。Main继承needCheckEncrypt=true且构造enabledSetDataEvent=true，与DataBase共享加密管理器单例；源路由/构造策略已定位，实际会话与对端接受仍未验证。五处直接字段写入限构造，其他管理器false不套用到BLE。见[BLE路由研究](../tools/research/BLE_ROUTE.md)（仓库根目录）及protocol/research/ronin-ble-route-evidence.json。未新增SDK收发/解密/高级功能，无硬件/liveUI/厂商执行，运行时0.7.29/0.3.29及完整命令false不变。


## 04:08 ACK与业务域研究

固定bank05独立核对20方法，基础表ACK剥离ccode后part/status对应原始payload1/2；GIMBAL回调成功仅返回码0，与业务SUCCESS1分开。短业务体不补PROCESSING；源混合命令key仅命令集/命令/序号，不照搬到SDK严格会话/ACK/端点关联。见[校准ACK研究](../tools/research/CALIBRATION_ACK.md)（仓库根目录）及protocol/research/ronin-calibration-ack-evidence.json。没有SDK发送/解密/高级新增、硬件/liveUI或厂商执行，运行时0.7.29/0.3.29及完整命令false不变。


## 0.7.30部件校准候选 / 原生0.3.30 build33

显式App来源新增sendComponentCalibrationRequest(sourcePart=AUTO)，同一操作槽内停主机运动、读取35反向bit0门槛、发送04:08/00并等待严格关联ACK；禁用不自动开电机，读取与ACK共用截止时间，不重发/重放。返回码、可不完整的业务part/status和物理完成分开，不更新其他校准/传感器/姿态缓存，不提供固件中止或高级等待组合。见 docs/APP_COMPONENT_CALIBRATION.md（仓库根目录）。实际会话/设备/物理效果待验收，完整命令门槛false；未操作硬件或实时UI。


## HG724手柄工厂与04:58键绑定研究

固定bank05核对19方法与注解，HG724条件工厂选择MobileHandheldControllerAbstraction；StickGimbalControlEnabled键支持和实际Setter注解对应04:58布尔类。方法名中的MicroPhones不定义功能，不新增麦克风/相机接口。工厂参数1是数量、普通index0，不改作接收地址；源链不证明现场反射/注册或固件效果。见[手柄绑定研究](../tools/research/HANDHELD_BINDING.md)（仓库根目录）及protocol/research/ronin-handheld-binding-evidence.json。未新增SDK收发/高级功能，无硬件/liveUI/厂商执行，运行时0.7.30/0.3.30及全命令false不变。


## 0.7.31手柄摇杆开关候选 / 原生0.3.31 build34

显式App来源新增sendHandheldStickControlRequest(enabled:boolean)，停止前验证/快照，同一操作槽内中位停止后一次04:58 bool00/01并等待严格关联ACK。不透明尾部保留，requestedEnabled不回写57缓存；无订阅/查询/重试/重放/反向回滚、摇杆接管或麦克风/相机/高级新增。见 docs/APP_HANDHELD_STICK_CONTROL.md（仓库根目录）。型号源链不等于实机效果或持久化，设备/物理/回读/通知关联标志false；未操作硬件/实时UI，完整命令门槛false。


## 0.7.32教程状态被动候选 / 原生0.3.32 build35

显式App来源下tutorialStatus（Python另有tutorial_status，原生appTutorialStatus）与kind=tutorial被动解码04:2B；保留步骤原值、完整32位无符号/有符号状态、9个数值标志、未知位与尾部，以及独立Java位移视图。未知步骤的源回退STEP_FINISH不是完成证明，bit30/31不解释为物理生命周期。缓存复制/不可变、观察者隔离，来源切换/断线清空；不发查询、订阅、ACK或04:2C，不结束查询或moveTo。本机布局/通知、请求关联及物理完成均未验收，完整命令和高级门槛仍false。契约见 docs/APP_TUTORIAL_STATUS.md（仓库根目录）。


## 04:40平衡调整请求与旧视图研究

固定六段61方法核对同命令发送/接收类、8个请求值、状态二进制字符串按十进制解析为0/1/10/11和非连续建议枚举；6个类外直接调用方法集中旧GimbalAdjustView。源attach可能关电机、20秒本地timer、错误/完成/超时发STOP，而detach未发STOP；不等于本机停止保证。见[平衡调整审计](tools/research/BALANCE_ADJUST.md)（仓库根目录）及protocol/research/ronin-balance-adjust-evidence.json。HG724入口、线上包层和物理效果未确认，未开放04:40 SDK收发、不替代balance_test/index37，无硬件/UI/厂商执行或高级新增，运行时仍0.7.32/0.3.32，全命令门槛false。


## 平衡入口型号条件与共享布局研究

固定六段30方法、4视图映射/3独立布局确认：有效所选项为HG724且BalanceCheck入口被调用时走GimbalVideoAdjustRS3，视频测试按钮GONE；两个新旧视频名共享同一布局/根类，不能连接为GimbalAdjustHG701的04:40发送。强制旧测试页可见说明是独立条件，不证明普通导航；限定字段引用扫描未建立旧调整页入口，也不证明固件不支持。见tools/research/BALANCE_ENTRY.md及protocol/research/ronin-balance-entry-evidence.json（仓库根目录）。没有新增SDK收发/高级功能或硬件/liveUI/厂商执行，运行时仍0.7.32/0.3.32，全部命令门槛false。


## 01/07备份槽位的独立审计

固定APK新增3137条（01段2623/07段514）备份到准确code_off ULEB槽位及方法owner数值索引的核对，复用完整长度/异常表/不重叠校验；不恢复字符串/类型/原型身份，不输出可解析DEX。前128KiB在01另涉及3111条type_ids，在07涉及全部type/proto及部分field_ids，不能只补字符串表。见tools/research/CODE_SLOTS.md及protocol/research/ronin-code-slots-evidence.json（仓库根目录）。既有六段具名恢复/调用扫描范围不变，不把01/07加入其BANKS；运行时仍0.7.32/0.3.32，无SDK收发/高级新增、硬件/liveUI/厂商执行，完整门槛false。
