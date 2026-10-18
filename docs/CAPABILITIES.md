# 非相机能力与证据边界

当前0.7.26 / 原生0.3.26为非相机控制项目，**不是全部 BLE 功能支持声明**。软件检查、其他型号的协议研究与 RS 4 Mini 实机证据分别列出。
设备 SDK 与上层组合的归属见 [ARCHITECTURE.md](ARCHITECTURE.md)；下表包含两层，不能把所有行都当作原生 BLE 能力。

| 能力 | 当前代码 | 证据与待办 |
|---|---|---|
| 三轴归一化速度、停止、整机回中 | 四端支持 | 基础协议沿用历史测试；新调度仍待统一实机验证 |
| 姿态、机械关节角、低速位置闭环 | 四端支持 | 保留本机已确认的字段和符号；约 1 Hz 反馈 |
| 速度关键帧轨迹 | 四端支持 | 线性/平滑/保持插值，取消和延误处理；开环，不保证物理路径精度 |
| 多路点定位、到位停留 | 四端支持 | 每点低速闭环和停止；不是固件原生轨迹程序 |
| 自动重连 | 四端显式启用 | 有界重试、手动退出取消；不恢复运动 |
| 保存位置、按轴返回 | 四端支持 | 绑定设备和实例；不是固件单轴回中 |
| 四元数读取和数学转换 | 四端支持显式顺序 | wxyz/xyzw、归一化、共轭和标准 ZYX；设备参考系仍未知 |
| 原生绝对角和原生角速度 | 显式 rs3 研究接口 | 部分 Pan 依据来自其他型号，RS 4 Mini 的轴、控制位及取消效果未证实 |
| 休眠/唤醒 | 显式 rs3/rs3mini 配置 | 两种配置字节不同，本机未验证 |
| 版本、位置、控制状态、类型查询 | 限定命令及响应关联 | 本机之前位置查询未收到有效响应；其他查询待验证 |
| 电量、校准进度、状态 TLV | 被动研究格式解析 | 标注型号和未验证状态；不自动启动不明的状态流或推算本机电量 |
| 固件单轴回中、完整跟随模式切换 | 部分源配置字段已封装；完整流程未验收 | 单轴回中无可靠证据；PF/PTF/FPV不能由单字段读写或旧枚举替代 |
| 自动调参、平衡测试、system_calc及电机/跟随参数 | 显式App来源设备SDK已提供部分请求/字段 | 完整字段、实际效果、持久化及固件中止仍未实机验收 |
| 固件内置轨迹、全景、延时摄影动作程序 | 未实现 | 其他型号的程序参数仍有推测字段；不能直接重放至本机 |
| 提高关节反馈频率、高精度连续位置控制 | 未确认可用 | 当前已测反馈约 1 Hz；不能把发送频率当作反馈频率 |
| 硬件急停、断链后可靠停止、绝对精度保证 | 不提供保证 | 软件中位帧和原生释放不等同固件已执行 |

相机快门、录像、对焦、镜头/图传和视觉跟踪均不在用户指定范围内。源码已提交 GitHub；npm 和远端二进制发布未执行。

下一阶段需要现场提供的证据：与屏幕逐项对照的新命令效果、明确姿态下的分轴采样、原生运动的停止表现，以及 Ronin App 非相机设置的受控通信样本。
官方应用静态分析已还原部分请求构造和型号链，完整覆盖仍未完成，见 [研究记录](RESEARCH_NEXT.md)。
开发期间没有进行扫描、连接、运动或批量命令探测。现场步骤见 `HARDWARE_CHECKLIST.md`，原始日志仍应放入被忽略目录。

0.7.1 已拆分设备 SDK 与高级封装，基础操作也经统一应用入口。新增 `requestDegreeInfo()` 仅提供关联原始响应。
完整底层命令前置验收未通过，因此不再新增高级功能；逐命令状态见 [SDK_COMMANDS.md](SDK_COMMANDS.md)。

0.7.2 新增研究配置下的被动用户参数响应/ACK 结构，不命名参数，不解释数值类型，不增加发送允许列表。
官方 App 枚举与资源事实扩充了候选清单，不等于 RS 4 Mini 的命令实现或本机验证。


0.7.3 显式当前App配置封装参数读取和HG724跟随灵敏度0/1读写；四端离线验证，未进行硬件验收。灵敏度不等于PF/PTF/FPV模式，剩余底层命令未完成。见 [APP_COMMANDS.md](APP_COMMANDS.md)。


0.7.4 设备SDK的显式当前App配置新增自定义跟随启用/三轴与电机启用/自拍限制/竖拍限制/360°Roll配置，语义来自继承源码；型号支持与实际效果未验证。没有新增高级运动或PF/PTF预设。见 [APP_SETTINGS.md](APP_SETTINGS.md)。


0.7.5 SDK提供显式来源的自动调参请求（无ACK）、校准状态查询与被动解码；主机发送、设备报告和物理完成分开。调参请求启动/false中止及通知条件未实机验证，电机数值调参/平衡测试/水平校准和其余命令未完成。见 [APP_CALIBRATION.md](APP_CALIBRATION.md)。


## 0.7.6 命名电机参数

0.7.6 已封装三轴刚度、强度、陀螺仪滤波和预控制，共12个命名参数，显式当前App配置下读04:32/写04:31；没有实机验收，不宣称HG724固件支持或全部电机能力完成。详见 [APP_MOTOR_TUNING.md](APP_MOTOR_TUNING.md)。


## 0.7.7 平衡测试SDK

四端封装0F/10命名平衡测试启动64与状态/三轴结果，零结果保留null，取消不发未证实的中止。Node102/Web14/Python两环境各80/native72+94+3/research42，类型/边界/构建通过。没有硬件、UI或高级新增；实机效果与全部命令仍未验收。详见 [APP_BALANCE_TEST.md](APP_BALANCE_TEST.md)。


## 0.7.8 system_calc自动校准

四端新增独立的普通0F/10/index36固定启动1和状态读取，与6A/6E自动调参分开。读取状态2/3不受写入范围0..1限制，未知值保留raw/null；ACK/报告不代表本次物理完成，取消不保证固件中止，无虚构写零停止。Node108/Web14/Python各86/native75+101+3/research45，类型/边界/构建通过。尚无水平校准身份或本机验收，未操作硬件/UI或新增高级任务。详见 [APP_SYSTEM_CALIBRATION.md](APP_SYSTEM_CALIBRATION.md)。


## 0.7.9 跟随/RC按轴档位

六组参数档位已同步四端，Pitch/Roll/Yaw字段为bits2..3/4..5/6..7，custom/low/middle/high为0/1/2/3；先读后改写，保留其他轴和未知低两位，共用操作槽和总截止时间。Node113/Web14/Python各91/native79+107+3/research49，类型/边界/构建通过；无硬件/UI/高级新增，PF/PTF和custom数值未因此完成。详见 [APP_FOLLOW_MODES.md](APP_FOLLOW_MODES.md)。


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


0.7.22新增[程序状态被动候选](APP_PROGRAM_STATUS.md)，不提供原生动作启动/停止，不自动查询/订阅/ACK或判定完成。


0.7.23新增[单次程序状态请求](APP_PROGRAM_REQUEST.md)：显式App来源、固定type2与三个命名程序，仅关联ACK、业务体不透明；不承诺新通知，不增加连续订阅或动作执行，本机未验收。


0.7.24新增[程序状态推送启停请求](APP_PROGRAM_SUBSCRIPTION.md)：显式program与布尔enabled，固定type0/1及关联ACK；不证明远端订阅状态、不自动维护或恢复订阅，不发送动作程序命令。本机仍未验收。


新增[轨迹路点与ActualPose审计](../tools/research/TRACK_POINTS.md)：UI秒数分段、首点/Roll规则及04:66缓存来源已核对，不能把原生轨迹角度直接当作现有机械关节角。仅研究，无SDK发送或硬件操作，运行时仍0.7.24/0.3.24，全命令门槛false。


0.7.25新增[外设状态源候选](APP_PERIPHERAL_STATUS.md)：46源类型/43 getter视图、保留tag21碰撞和GPS整数截断；不改现有姿态/关节，不自动ACK/订阅或控制，本机未验收。


新增[完整订阅键与初始化条件审计](../tools/research/SUBSCRIPTION_CATALOG.md)：152个注册键分开记录显式索引、21个元数据条件键与2个型号条件；不将缺失0或资源预期索引自动变成SDK发送表。仅离线研究，运行时仍0.7.25/0.3.25，全命令门槛false。


0.7.26新增[单次命名参数订阅请求](APP_PARAMETER_SUBSCRIPTION.md)：固定DB已加载/HG724静态分支、152命名键、CENTER/id7无ACK，仅一次请求。没有空集停止、后台刷新或重连重放；本机路由/通知/远端状态仍未验收，不改变完整命令及高级门槛。


## 外设数据04:69源审计（运行时不变）

固定六段36方法、12数据类型/4来源枚举，核对tag2的控制来源及三轴signed16原值、无ACK start、空doPack和基础双路分发。仅定位跟踪界面读取两轴的一个直接调用者，无HG724或物理单位/路由证据。源旧字段保留/短包只清速度与离线独立帧视图区分；未增加SDK收发、相机/视觉或高级功能。见[EXTERNAL_DEVICE.md](../tools/research/EXTERNAL_DEVICE.md)和protocol/research/ronin-external-device-evidence.json。运行时仍0.7.26/0.3.26，全部命令及高级门槛false，无硬件/实时UI/厂商执行。
