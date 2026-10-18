# Python SDK 0.7.31

Python 3.8+、Bleak 后端。保留早期 camelCase 和 snake_case 调用，同时补充反馈、低速位置闭环、缓存 ID、停止取消和 `close()`。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

```python
import asyncio
from rs4mini_sdk import RS4Mini

async def main():
    gimbal = RS4Mini(deviceId=None, ioTimeoutMs=3000)
    try:
        await gimbal.connect(timeoutMs=30000)
        print(await gimbal.getJointAngles(fresh=True))
    finally:
        await gimbal.close()

asyncio.run(main())
```

## API

- `connect(timeoutMs=30000, directConnectTimeoutMs=5000, deviceId=...)`：总连接截止时间；缓存 ID 直连失败后扫描。旧参数 `timeout` 为秒，不能和 `timeoutMs` 同时指定。
- `setVelocity(pan=0, tilt=0, roll=0)` / `set_velocity(...)`：标准化输入，-1..1。
- `setVelocityDeg(...)` / `set_velocity_deg(...)`：经验角速度换算。
- `moveFor(durationMs=500, pan=0.05)`；旧别名 `move_for(duration, ...)` 的时长为秒。
- `getAttitude(fresh=False, timeoutMs=3000)` / `get_attitude(fresh=False, timeout_ms=3000)`。
- `getJointAngles(...)` / `get_joint_angles(...)`：返回字典，含 pitch/roll/yaw、raw、unit、timestamp。
- `moveTo(pan=..., tilt=..., roll=..., toleranceDeg=1, timeoutMs=30000, telemetryTimeoutMs=3000, gain=0.02, minSpeed=0.05, maxSpeed=0.18)`；`move_to` 使用对应下划线参数。
- `stop()`：取消位置/限时运动并等待清理；`recenter()` 为三轴回中。
- `disconnect()`：可重用；`close()`：永久关闭实例；异步上下文管理器退出使用 `close()`。

位置目标为机械关节角，Pan=Yaw、Tilt=Pitch、Roll=Roll。反馈约 1 Hz。已进入容差的轴归零；Pan 用最短环绕差。默认参数与 Node 一致。

有限运动、初次写入及停止清理期间互斥。冲突抛 `RS4MiniError.code == 'RS4MINI_BUSY'`。先创建并保存运动任务，再调用 `stop()`，并处理旧任务的 `RS4MINI_MOVE_CANCELLED`。外部 `task.cancel()` 保留 `asyncio.CancelledError`，同样清理；旧限时睡眠不会影响新命令。

错误码还包括 `RS4MINI_MOVE_TIMEOUT`、`RS4MINI_TELEMETRY_TIMEOUT`、`RS4MINI_CONNECT_TIMEOUT`、`RS4MINI_CONNECT_CANCELLED`、`RS4MINI_IO_TIMEOUT`、`RS4MINI_DISCONNECTED`。位置总超时携带 `target` 和 `current`（无样本时为 None）。每次 BLE 写入与清理受 `ioTimeoutMs` 限制；失败后断开。后端需遵守 asyncio 取消约定；无法通过软件保证失去蓝牙后的物理停止。

回调 `onNotification/onMessage/onTelemetry/onDisconnect/onError` 支持同步或异步函数；对应 `on_notification/on_message/on_telemetry/on_disconnect/on_error` 别名。反馈、速度与回调参数使用副本。导出的 `DumlStreamDecoder`、`parse_duml_frame`、`decode_gimbal_telemetry` 不需要实际蓝牙设备。

运行 `examples/telemetry_capture.py` 只读取反馈；`examples/position_demo.py` 会移动，先确认平衡和空间。新行为尚待 [实机清单](../docs/HARDWARE_CHECKLIST.md) 验证。
## 0.7.2 非相机扩展

`enableAutoReconnect()` / `enable_auto_reconnect()`：显式启用有界退避重连。
默认五次、500 ms 起步、二倍退避、上限 10 s；回调 `onReconnect` / `on_reconnect`、
状态副本 `reconnectState` / `reconnect_state`。仅恢复链路，不重放旧速度和轨迹。
`disconnect()`、`close()`、`await disable_auto_reconnect()` 取消策略与正在进行的重试。

`runTrajectory(keyframes, interpolation='linear', maxLagMs=500)` 或
`run_trajectory(keyframes, interpolation='linear', max_lag_ms=500)` 按 timeMs 速度关键帧执行。
keyframes 示例：`[{'timeMs':0,'pan':0.05},{'timeMs':1000,'pan':0}]`。
linear/smoothstep/step 插值共用串行写入、单调时钟与跳过迟到采样点的策略；结束或错误发送停止。
这是开环速度轨迹，不能保证物理速度或角度精度。

`moveThrough([{'pan':5,'holdMs':1000},{'pan':0}], timeoutMs=30000)` 逐点闭环定位并停止、停留。
timeoutMs 分别限制每段，停留不计入下段；snake_case 为 `move_through(..., timeout_ms=...)`。
两种轨迹均保持完整运动所有权，`stop()` 取消整条流程；进度副本为 `trajectory_progress`。

`await capture_home(fresh=True)` 保存当前关节位置，`await move_home(axes=['pan'])` 仅返回指定轴。
保存值限当前实例与设备。它不等于固件单轴回中。

`get_orientation(component_order='wxyz', conjugate=False, fresh=True)` 支持显式指定 wxyz/xyzw
并转换为标准右手内禀 ZYX 欧拉角，模长容差默认 0.1；短帧不会满足等待。
纯函数 `orientation_from_components()` 可离线使用。设备分量约定仍未实测，结果带有
`deviceConventionVerified=False`，不自动用于位置闭环。

`gimbal.experimental.use_profile('rs3')` / `'rs3mini'` 开启显式研究配置。
支持 `query(kind='version'|'position'|'controlStatus'|'type')`、`set_sleep(asleep=True)`，
以及 rs3 配置下的 `absolute(pan=2,parameterByte=20,observeMs=3000)`、
`rate_for(pan=2,duration_ms=500)`；含义及边界与 Node 实验接口一致，参见 `../node/API.md`。
查询匹配连接、序号、端点、命令和响应位；超时取消排队写入，已经开始的帧有界完成。
实验状态副本为 `experimental.status`，通知回调为 `on_experimental_status`。
原生速率停止先释放再发送中位帧；物理执行/到位均未证实，不能据此声称完整支持 RS 4 Mini。

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


## 0.7.28传感器校准被动候选 / 原生0.3.31 build31

显式App来源下sensorCalibrationStatus/kind=sensorCalibration解析04:30两字节源进度/状态及尾部，保留0..255原值，映射0/1/3/9并标记未知；不复用08状态或旧inProgress，不补短包默认，不由COMPLETE结束查询/运动。缓存复制/不可变、观察者隔离、来源/断线清空。见[传感器校准候选SDK](../docs/APP_SENSOR_CALIBRATION_STATUS.md)。没有查询/订阅/自动ACK/校准触发或相机/视觉/高级新增；本机/单位/请求关联与物理完成未验收，无硬件/liveUI/厂商执行，全命令门槛false。此前当前App30“未接SDK”限定为历史状态。


## 0.7.29接收业务解析边界 / 原生0.3.29 build32

关联App ACK、04:05反馈、04:6E调参通知和旧研究状态拒绝加密/无效flags，原始帧保持可观察；加密读取不推进参数写入，加密关节不进入定位反馈。没有新增命令、解密、协商、硬件操作或高级功能，完整命令与高级门槛仍false。契约见 docs/PLAINTEXT_BOUNDARIES.md（仓库根目录）；本版本取代此前宽松解析行为，历史版本记录保留。


## 0.7.30部件校准候选 / 原生0.3.30 build33

显式App来源新增sendComponentCalibrationRequest(sourcePart=AUTO)，同一操作槽内停主机运动、读取35反向bit0门槛、发送04:08/00并等待严格关联ACK；禁用不自动开电机，读取与ACK共用截止时间，不重发/重放。返回码、可不完整的业务part/status和物理完成分开，不更新其他校准/传感器/姿态缓存，不提供固件中止或高级等待组合。见 docs/APP_COMPONENT_CALIBRATION.md（仓库根目录）。实际会话/设备/物理效果待验收，完整命令门槛false；未操作硬件或实时UI。


## 0.7.31手柄摇杆开关候选 / 原生0.3.31 build34

显式App来源新增sendHandheldStickControlRequest(enabled:boolean)，停止前验证/快照，同一操作槽内中位停止后一次04:58 bool00/01并等待严格关联ACK。不透明尾部保留，requestedEnabled不回写57缓存；无订阅/查询/重试/重放/反向回滚、摇杆接管或麦克风/相机/高级新增。见 docs/APP_HANDHELD_STICK_CONTROL.md（仓库根目录）。型号源链不等于实机效果或持久化，设备/物理/回读/通知关联标志false；未操作硬件/实时UI，完整命令门槛false。
