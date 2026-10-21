# RS 4 Mini Control 0.3.42 / build 45

本版将方向按钮改为边框内居中绘制，并加入本窗口方向键控制：↑/↓对应Tilt正/负，←/→对应Pan负/正，驱动力沿用滑块。按住移动、松开停止，可同时按航向和俯仰方向；相反方向抵消。输入框、下拉框、滑块、弹窗和修饰键组合不接管。失焦、断开、点击其他控件或停止后清空按键状态，系统自动重复不会恢复旧运动；重新按键才能继续。无需系统辅助功能或全局键盘监听权限。键盘仅复用既有SDK速度/停止接口，无新协议。

上一版修复右侧面板首次显示时横向越界、滚动后才恢复的问题：滚动文档从局部坐标0开始，宽度跟随视口，首次定位前完成布局。`sh macos/check-layout.sh` 使用同一生产创建入口，在820/600高度验证全部32项操作及滚动前后边界，不创建蓝牙管理器。下方旧版本功能描述为历史，当前范围见主README和接口清理说明。

此前变更：移除手柄查询与主动调参状态查询；电机默认/筛选多项改为逐项读取后完整汇总，非原子快照，保留各次真实响应。被动进度通知保留。详见仓库docs/APP_MOTOR_TUNING.md；下文旧版本新增记录是历史。

当前右侧「设备 SDK」面板：32 个命名 App 来源操作、4 类保留被动状态、原始 degree-info 查询，复用同一个 RSGimbal。使用与验证范围见 [面板说明](../docs/MACOS_SDK_PANEL.md)。

Objective-C / AppKit / CoreBluetooth 原生面板，提供三轴按住速度控制、停止、三轴回中、姿态/机械关节反馈和低速关节目标定位，不依赖 Node 或 Python。

```sh
sh macos/test.sh
sh macos/build.sh
open "macos/RS 4 Mini Control.app"
```

构建需要 Xcode Command Line Tools；生成的应用使用本地 ad-hoc 签名。

连接后等待反馈，目标框默认填入当前机械角。勾选 Pan/Tilt/Roll 中要控制的轴，修改角度并点击低速定位。目标范围 -180..180° 不代表机械安全范围。固定参数：容差 1°、总超时 30 秒、反馈看门狗 3 秒、gain 0.02、最小速度 0.05、最大速度 0.18。Pan 为最短环绕差，Tilt 使用已验证的反号，已到位轴逐轴归零。

方向按钮按住运动，松开停止；驱动力为虚拟摇杆输入。定位和停止清理期间禁止新运动，点击停止可取消定位或尚未发送的回中。连接各阶段共享 30 秒截止时间，支持取消连接。意外断线不恢复运动。可显式勾选自动重连：按原设备 ID 过滤，500 ms 起步、倍增、上限 10 秒、最多 5 次；每次连接限 30 秒。手动断开、退出或取消勾选会关闭重试策略。

发送队列遵守 CoreBluetooth 背压，20 字节分片不交错。停止保留已开始帧的剩余分片，丢弃排队运动，再发送三个中位帧；发送超过 3 秒无进展则清理并断开。停止帧提交给 CoreBluetooth 不等于已收到设备确认。

窗口/应用失焦请求停止，退出先断开并等待清理，最多等待 5 秒。首次运行需要系统蓝牙权限。负载平衡、实际停止效果和控制精度必须现场验证。

`RSControlCore` 的离线测试涵盖黄金帧、半步舍入、CRC/分片重组、停止队列、位置方向、逐轴容差、环绕和超时；编译通过不代表系统蓝牙回调或新位置 UI 已实机验证。参见 [统一实机清单](../docs/HARDWARE_CHECKLIST.md)。

## 新增入口

窗口可纵向滚动。等待新关节反馈后，“保存当前位置”记录本设备的位置；“选中轴返回保存位置”使用上方 Pan/Tilt/Roll 勾选项，只返回所选轴。这与固件回中零点不同。

在速度关键帧、关节路点、实验指令中选择文件类型，载入 JSON 后需另行点击执行。
格式和可载入样例见 `../examples/motions/`。速度轨迹使用 smoothstep、15 Hz，调度/链路延误 500 ms 触发取消；路点逐点到位、停止并停留。停止、失焦和断线取消整条流程，不进入后续路点。

实验 JSON 必须明确 profile=rs3/rs3mini，支持 observe、query、sleep，以及 rs3 配置的 absolute、rate。
字段同 `../node/API.md` 中的接口，另加 command/profile；原生查询独占操作槽。原生速率结束或停止先发送零速/释放，再发三个中位帧。
观察时间不是固件执行时间，写入、函数结束或查询 ACK 均不代表物理到位。没有启用校准触发、任意命令发送或相机控制。

四元数区要求显式选择 wxyz/xyzw，可选共轭；仅进行标准 ZYX 数学转换，设备参考系未确认且不参与运动闭环。
本轮只构建和测试，未启动含真实 CoreBluetooth 管理器的应用，可视布局待解锁后统一检查。

## 分层与前置条件

本版将设备访问与高级运动分为两个模块。应用继续使用原有 `RS4Mini`（原生为 `RSGimbal`）一个入口，
基础操作也通过它访问设备 SDK；不新建第二条连接。底层命令尚未全部解析/验收，在此之前不新增高级功能。
模块映射和限制见 [架构边界](../docs/ARCHITECTURE.md)，命令证据见 [设备命令审计](../docs/SDK_COMMANDS.md)。


当前 App 来源参数 SDK 提供显式配置下的参数读取和跟随灵敏度读写，复用既有连接。调用入口、各端差异与未验收边界见 [参数 SDK](../docs/APP_COMMANDS.md)。全部底层命令仍未完成，高级功能开发继续暂停。


0.7.4 新增显式当前App来源的自定义跟随与电机设置位字段读取/修改；保留其他位、共享事务截止时间和操作槽。入口及未验收边界见 [命名设置SDK](../docs/APP_SETTINGS.md)。


0.7.5 封装当前型号路径的无ACK自动调参请求、校准状态查询/通知，严格区分本机写入、设备报告与物理完成。接口和待验收边界见 [调参请求与状态](../docs/APP_CALIBRATION.md)。


0.7.6新增十二个命名电机数值参数的31/32读写，和普通用户参数命令空间分开；源码范围与实际设备效果分别验收。见 [电机参数SDK](../docs/APP_MOTOR_TUNING.md)。


0.7.7（原生0.3.7）新增平衡测试启动请求和状态/三轴结果读取，应用统一入口和显式当前App配置不变。接口、端差异和固件停止/完成未验收边界见 [APP_BALANCE_TEST.md](../docs/APP_BALANCE_TEST.md)。


0.7.8（原生0.3.8）新增sendAutoCalibrationRequest/getAutoCalibrationStatus及各端等价接口，与6A/6E自动调参分开。完整API、端差异和未验收边界见 [APP_SYSTEM_CALIBRATION.md](../docs/APP_SYSTEM_CALIBRATION.md)。


0.7.9（原生0.3.9）新增get/setFollowSettings与get/setRcSettings及各端等价接口：六组参数按轴custom/low/middle/high档位，先读后改写，保留其他轴和低两位。接口与未验收边界见 [APP_FOLLOW_MODES.md](../docs/APP_FOLLOW_MODES.md)。


0.7.10（原生0.3.10）新增get/setFollowTuning与get/setRcTuning及各端等价接口：18项普通命名数值、1/2字节小端、异常读值保留，不自动切档位/预设/输入源。接口与未验收边界见 [APP_NUMERIC_TUNING.md](../docs/APP_NUMERIC_TUNING.md)。


0.7.11（原生0.3.11）新增getStandaloneTuning/setStandaloneTuning，Python另有snake_case别名。六项独立配置必须显式inputSource:2，并与数值同包写入；读取保留实际输入源，无自动切换/重放/回滚，活动预设和实机效果未验收。见 [APP_STANDALONE_TUNING.md](../docs/APP_STANDALONE_TUNING.md)。


0.7.12（原生0.3.12）新增固定04:24被动用户参数缓存，17个源码getter原值，显式App配置、至少74字节、请求型且未加密；不发订阅或改变姿态反馈。onAppStatus按kind区分calibration/userParameters。接口与本机未验收边界见 [APP_USER_PARAMETERS.md](../docs/APP_USER_PARAMETERS.md)。


0.7.13（原生0.3.13）新增getHandleSettings及Python别名/原生等价接口，显式App来源下04:36空体只读查询，8个业务字段保留原值和源bit0、尾字节保留；不写入或推断profile等价关系。见 [APP_HANDLE_SETTINGS.md](../docs/APP_HANDLE_SETTINGS.md)。


0.7.14（原生0.3.14）新增sendFineTuneRequest及Python别名/原生等价方法，显式App配置、Pitch/Roll、adjustmentDegrees有限-2..2，按float32编码并独占到ACK；不声明实际角度/累加或暂停状态，也不自动暂停/回滚。见 [APP_FINE_TUNE.md](../docs/APP_FINE_TUNE.md)。


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


0.7.20新增[手柄状态被动候选](../docs/APP_HANDHELD_STICK.md)，仅显式App来源、无58发送/订阅，真实57布局、单位与轴映射等待本机验收；未新增高级功能。


0.7.21新增[异常与电量被动候选](../docs/APP_SOURCE_STATUS.md)，显式App来源、原始位/255保留，不触发请求或自动控制；本机布局与通知仍未验收。


0.7.22新增[程序状态被动候选](../docs/APP_PROGRAM_STATUS.md)：显式App来源下38/64/6B独立帧快照，未知/重复记录保留，无查询/订阅/自动ACK，不等于物理完成；完整命令仍未验收。


0.7.23新增[单次程序状态请求](../docs/APP_PROGRAM_REQUEST.md)：显式App来源、固定type2与三个命名程序，仅关联ACK、业务体不透明；不承诺新通知，不增加连续订阅或动作执行，本机未验收。


0.7.24新增[程序状态推送启停请求](../docs/APP_PROGRAM_SUBSCRIPTION.md)：显式program与布尔enabled，固定type0/1及关联ACK；不证明远端订阅状态、不自动维护或恢复订阅，不发送动作程序命令。本机仍未验收。


0.7.25新增[外设状态源候选](../docs/APP_PERIPHERAL_STATUS.md)：46源类型/43 getter视图、保留tag21碰撞和GPS整数截断；不改现有姿态/关节，不自动ACK/订阅或控制，本机未验收。


## 0.7.26单次命名参数订阅 / 原生0.3.26 build29

显式App来源下发送固定DB已加载/HG724静态分支的152命名键非空单次04:12请求，CENTER/id7、无ACK；报告21元数据和2型号条件键。不提供空集停止、后台刷新、反向请求或重连重放；三条中位前导及独占操作槽，不由发送成功判断远端订阅、通知新鲜度或物理效果。详见[单次参数订阅](../docs/APP_PARAMETER_SUBSCRIPTION.md)。此版本扩展此前“仅研究/工作树开发”的历史状态；实际型号/路由/通知/远端停止仍待验收，全命令及高级门槛false，无硬件/实时UI/厂商执行。


## 0.7.27外设数据被动候选 / 原生0.3.27 build30

显式App来源下externalDeviceStatus/kind=externalDevice解析04:69完整TLV，tag2保留来源及三轴signed16原值、未知/重复与尾字节；Other7与未知原值分开，不继承源单例旧值或短包清零副作用。来源/断线清空，观察者隔离；不发送/订阅/自动ACK，不完成查询或改变姿态/关节、运动所有权。见[外设数据候选SDK](../docs/APP_EXTERNAL_DEVICE_STATUS.md)。本机布局/单位/参考系均未验收，未新增相机/视觉/高级功能，无硬件/liveUI/厂商执行，全命令门槛false；此前“仅研究未接SDK”为历史状态。


## 0.7.31传感器校准被动候选 / 原生0.3.28 build31

显式App来源下sensorCalibrationStatus/kind=sensorCalibration解析04:30两字节源进度/状态及尾部，保留0..255原值，映射0/1/3/9并标记未知；不复用08状态或旧inProgress，不补短包默认，不由COMPLETE结束查询/运动。缓存复制/不可变、观察者隔离、来源/断线清空。见[传感器校准候选SDK](../docs/APP_SENSOR_CALIBRATION_STATUS.md)。没有查询/订阅/自动ACK/校准触发或相机/视觉/高级新增；本机/单位/请求关联与物理完成未验收，无硬件/liveUI/厂商执行，全命令门槛false。此前当前App30“未接SDK”限定为历史状态。


## 0.7.29接收业务解析边界 / 原生0.3.29 build32

关联App ACK、04:05反馈、04:6E调参通知和旧研究状态拒绝加密/无效flags，原始帧保持可观察；加密读取不推进参数写入，加密关节不进入定位反馈。没有新增命令、解密、协商、硬件操作或高级功能，完整命令与高级门槛仍false。契约见 docs/PLAINTEXT_BOUNDARIES.md（仓库根目录）；本版本取代此前宽松解析行为，历史版本记录保留。


## 0.7.30部件校准候选 / 原生0.3.30 build33

显式App来源新增sendComponentCalibrationRequest(sourcePart=AUTO)，同一操作槽内停主机运动、读取35反向bit0门槛、发送04:08/00并等待严格关联ACK；禁用不自动开电机，读取与ACK共用截止时间，不重发/重放。返回码、可不完整的业务part/status和物理完成分开，不更新其他校准/传感器/姿态缓存，不提供固件中止或高级等待组合。见 docs/APP_COMPONENT_CALIBRATION.md（仓库根目录）。实际会话/设备/物理效果待验收，完整命令门槛false；未操作硬件或实时UI。


## 0.7.31手柄摇杆开关候选 / 原生0.3.31 build34

显式App来源新增sendHandheldStickControlRequest(enabled:boolean)，停止前验证/快照，同一操作槽内中位停止后一次04:58 bool00/01并等待严格关联ACK。不透明尾部保留，requestedEnabled不回写57缓存；无订阅/查询/重试/重放/反向回滚、摇杆接管或麦克风/相机/高级新增。见 docs/APP_HANDHELD_STICK_CONTROL.md（仓库根目录）。型号源链不等于实机效果或持久化，设备/物理/回读/通知关联标志false；未操作硬件/实时UI，完整命令门槛false。


## 0.7.32教程状态被动候选 / 原生0.3.32 build35

显式App来源下tutorialStatus（Python另有tutorial_status，原生appTutorialStatus）与kind=tutorial被动解码04:2B；保留步骤原值、完整32位无符号/有符号状态、9个数值标志、未知位与尾部，以及独立Java位移视图。未知步骤的源回退STEP_FINISH不是完成证明，bit30/31不解释为物理生命周期。缓存复制/不可变、观察者隔离，来源切换/断线清空；不发查询、订阅、ACK或04:2C，不结束查询或moveTo。本机布局/通知、请求关联及物理完成均未验收，完整命令和高级门槛仍false。契约见 docs/APP_TUTORIAL_STATUS.md（仓库根目录）。


## 0.7.33 CENTER只读信息候选 / 原生0.3.33 build36

显式App来源新增getCenterActivationInfo（Python另有get_center_activation_info，原生RSGimbal继承同名selector），要求sourceVersion四种已知格式，无默认/OTHER/协商。固定E5/CENTER-id7、COMMON00:32 GET01/11与严格关联明文ACK；完整本次业务体解析active/date/SN原始值及源signed-decimal字符串、尾部，无旧SN缓存成功回退。GIMBAL04:32同命令号隔离，原生完成后恢复普通04路由；无激活/绑定/SET/FAIL/自动回复/重试/重放或高级新增。见[接口契约](../docs/APP_CENTER_INFO.md)（仓库根目录）。设备/当前版本/布局/激活有效性未验收，全命令及高级门槛false，无硬件/liveUI/厂商执行。
