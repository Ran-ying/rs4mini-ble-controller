# 蓝牙设备 SDK 与上层组合能力的边界

2026-10-16。用户明确要求区分“蓝牙到稳定器”和“基于 SDK 组合更多功能”。
本文件定义能力与维护边界。0.7.1 已完成两个运行时模块的拆分；应用始终使用高级封装入口，
基础设备操作也从此入口调用。完整命令前置条件仍未满足，见 [SDK_COMMANDS.md](SDK_COMMANDS.md)。

## 姿态和关节角

- **姿态（attitude）**：描述相机平台的方向，包括抬头/低头、左右朝向和画面倾斜。
  本设备的参考零点、全部坐标约定尚未完全确认，不能把 yaw 直接当作地理方位角。
- **关节角（joint angles）**：描述三组机械转轴各自的转角，是机构内部的配置量；
  零点按设备反馈解释，不自动等于画面水平或镜头朝前。
- 两者都可能用 pitch/roll/yaw 命名，但含义和数值不相同。手柄倾斜时，电机可以改变关节角来补偿，
  使相机平台方向大致保持不变。三轴机构的关节角不能分别简单地从姿态角相减得到。
- 当前 `getAttitude()` 读姿态字段，`getJointAngles()` 读关节字段；`moveTo()` 目标是关节角，
  不表示把镜头指向给定的世界方向。两种 getter 消费已有通知或等待下一帧，不主动查询设备。

## 分层责任

| 层 | 负责什么 | 边界 |
|---|---|---|
| 蓝牙设备 SDK | 连接/断开、通知、DUML 编解码和响应关联、设备命令、反馈解码、写入串行化和截止时间 | SDK 方法不必与一条固件命令一一对应；标明实际设备协议及证据 |
| 运动组合层 | 根据时间、反馈和目标调用设备 SDK；限时运动、位置闭环、路点、关键帧、保存位置返回 | 运行在电脑；组合功能不是新增的固件 BLE 能力 |
| 应用层 | Web/原生面板、文件选择、参数编辑、任务展示及应用策略 | 使用前两层；按钮存在不证明实机验收完成 |

设备 SDK 可以包含必要的软件机制，例如重连、缓存、分片、持续发送和写入队列。
归属取决于它是在提供可靠设备访问，还是在表达用户的运动目标和任务。
稳定器内部防抖、传感融合和电机实时闭环由固件执行。
电脑约 15 Hz 的指令发送频率不是电机控制频率；已测关节反馈约 1 Hz。

## 现有 API 归属

| 现有入口 | 归属与执行位置 | 设备协议关系 |
|---|---|---|
| 连接/断开/关闭、自动重连 | 设备 SDK 链路管理，运行在电脑 | 重连是主机策略，不是新增固件功能；不恢复旧运动 |
| `setVelocity()` | 设备 SDK；主机持续发送归一化虚拟摇杆输入 | 已确认 `04:01`；不是精确度/秒命令 |
| `getAttitude()` / `getJointAngles()` / `onTelemetry` | 设备 SDK；从通知解码并缓存 | 已确认 `04:05` 字段；getter 没有额外主动查询 |
| `recenter()` | 设备 SDK 的原生三轴回中操作，包含先停止的主机清理 | 已确认 `04:4C`，固件执行回中；不提供单轴选择 |
| `stop()` | 跨层停止：先取消主机运动任务，再由设备 SDK 发送中位帧 | 沿用 `04:01` 三次中位；不是独立硬件急停，也没有固件执行确认 |
| `setVelocityDeg()` | 运动组合层的经验单位换算 | 最终仍是虚拟摇杆；不等于原生角速度控制 |
| `moveFor()` / `moveTo()` | 运动组合层的计时/反馈闭环，运行在电脑 | 使用已有速度、停止和关节反馈，没有原生到位指令 |
| `runTrajectory()` / `moveThrough()` | 运动组合层的关键帧或逐点任务 | 主机持续执行，不能上传后脱离电脑独立运行 |
| `captureHome()` / `moveHome()` | 运动组合层保存关节角、按轴调用闭环定位 | 返回用户保存位置，不是固件单轴回中 |
| 四元数原始分量 / `getOrientation()` | 原始分量属设备反馈；顺序配置、归一化与欧拉角转换属数学工具 | 设备坐标约定仍未验证；不代表姿态目标控制已实现 |
| `experimental.query()` / `setSleep()` | 隔离的实验设备协议接口 | 来自 rs3/rs3mini 配置，本机未验证 |
| `experimental.absolute()` / `rateFor()` | 实验设备命令加主机观察/计时/清理 | 原生命令候选不等于已验证设备能力；函数返回不等于物理到位 |

## 剩余需求的可行性

下表是根据当前源码和协议证据作出的工程判断，不能替代实机验证。

| 需求 | 能否用现有速度和反馈组合 | 难点与剩余边界 |
|---|---|---|
| 指定轴返回目标/保存位置 | 可以，当前已实现低速关节定位和选轴返回 | 验收负载下的停止效果；固件定义的单轴回中命令、零点与补偿行为仍未知 |
| 定点扫描、停留、动作序列 | 可以，当前路点/速度关键帧可作为基础 | 基础编排较直接；连续平滑路径、准时到达和物理精度需要进一步控制设计 |
| 连续精确角度/姿态轨迹 | 可研究低速近似，不能保证任意精度或速度 | 约 1 Hz 反馈、未知坐标变换与原生控制语义是限制；更快反馈需新证据 |
| PF/PTF/FPV 等固件跟随模式切换 | 仅控制某些轴不等于切换固件模式 | 需模式设置/读取协议；现有反馈不足以保证等效复现手柄跟随 |
| 自动整定、校准、电机刚度等内部参数 | 现有速度和角度反馈不能替代 | 需参数/触发/进度协议；研究与验收较难，上层运动不能冒充固件校准 |
| 全景扫描、延时运动的角度与等待流程 | 可以组合运动部分，需主机持续运行 | 固件内置程序需上传/启动/状态/取消协议；相机快门不在范围内 |
| 休眠/唤醒、版本、电量等 | 不能从速度和关节角推导可靠设备设置/读数 | 需各自协议与字段证据；已有实验编码，难点在本机兼容性确认 |

官方手册介绍了跟随模式、自动整定与刚度等设备功能；这些介绍不提供本项目所需的 BLE 命令格式。
来源：[DJI RS 4 Mini 用户手册](https://dl.djicdn.com/downloads/DJI_RS4_Mini/20250220/UM-mini/RS4_Mini_User_Manual_en.pdf)。
已知命令、跨型号研究来源和未知字段以 [PROTOCOL.md](PROTOCOL.md) 为准。

## 实现与验收规则

1. 设备 SDK 以明确的功能矩阵验收，分别记录协议来源、型号/固件、写入与响应、物理效果。
   不使用无法枚举的“全部 BLE 功能”作为完成标准；研究候选、设备不支持、暂未验证要分开标识。
2. 运动组合层只依赖设备 SDK 契约，不直接构造或写 BLE 帧。设备层须能独立使用，不依赖轨迹或 UI。
   停止、取消、写入所有权统一协调，不能因分层产生绕过互斥的第二条写入路径。
3. 0.7.1 保持现有 `RS4Mini` 公共入口兼容，以继承复用设备 SDK 和共享操作协调器。
   基础方法由底层实现并通过上层对象提供；高级方法只调用底层命令契约，不构造或写 BLE 帧。
   不创建第二个连接或队列；新增 `requestDegreeInfo()` 只返回关联原始响应。
4. Python/Web/原生使用相同能力边界，保留各端实现差异。设备协议与上层任务分别验收。
   新增运动等待用户返回并要求测试后，按统一清单执行实机验证。

## 实际模块与应用入口（0.7.1 / 原生 0.3.1）

| 端 | 设备 SDK 模块 | 应用唯一入口 | 组合实现 |
|---|---|---|---|
| Node | `node/src/device.js`、`experimental-device.js`；维护入口 `rs4mini-sdk/device` | 包根导出的 `RS4Mini` | `controller.js`、`experimental.js` |
| Python | `rs4mini_sdk/device.py`、`reconnect.py`、`experimental_device.py` | `from rs4mini_sdk import RS4Mini` | `controller.py`、`expansion.py`、`experimental.py` |
| Web | 共享 JS 设备 SDK 与 `web/adapter.js` | `web/rs4mini.js` 的 `RS4Mini` | 共享 JS 高级封装；页面使用该入口 |
| 原生 | `RSBleDevice`、`RSDeviceProtocol.h`/`RSControlCore.m` | `RSGimbal` | `RSGimbal.m`、`RSMotionCore` |

设备 SDK 可以单独加载/链接，且不包含位置、轨迹或保存位置操作。共享操作协调器属于底层协作契约，
上层在其作用域内请求速度/读取/停止，防止任务间交叉写入。原生使用同一队列和调度器上的扩展钩子。
旧的纯协议函数导出和 `RSControlCore.h` 聚合头为兼容保留，不是 UI 的设备控制入口。
`tools/check-boundaries.py` 检查依赖方向和上层不得构造/写包；新测试验证底层独立加载/链接与上层使用同一写入路径。

用户要求的开发顺序为：先完成两层拆分，再补齐设备命令证据/解码/封装并验收，最后继续新增高级功能。
当前处于第二步。保留和回归已有高级功能不表示跳过该前置条件。


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


[HG724支持键规则研究](../tools/research/KEY_SUPPORT.md)区分声明支持谓词、缓存动作注册与原生BLE命令；保留多匹配歧义，不据键数量声明协议完整或新增发送。


[HG724初始化与动作声明分派](../tools/research/REGISTRATION.md)补齐继承目录及两个动作的静态声明链，仍非运行时注册或本机验收；不改变SDK发送与高级门槛。


[固件动作程序通用源审计](../tools/research/PROGRAMS.md)核对62/25/37/63请求与38/64/6B状态差异；仅静态业务体证据，尚无HG724完整路径或SDK新增发送，全命令门槛false。


[程序菜单与HG724条件分类](../tools/research/PROGRAM_ENTRY.md)补齐产品缓存/布局声明链，区分快门线帮助与检查函数可达性；尚未证明完整型号工作流，不新增发送或高级功能。


[主页面挂载与轨迹UI工作流](../tools/research/TRACK_WORKFLOW.md)补齐静态挂载链，区分ACK后的界面状态、重订阅和物理停止；仍未开放程序SDK或高级功能。
