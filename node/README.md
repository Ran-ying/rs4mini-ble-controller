# RS4 Mini Node.js SDK 0.7.36

当前变更：移除手柄查询与主动调参状态查询；电机默认/筛选多项改为逐项读取后完整汇总，非原子快照，保留各次真实响应。被动进度通知保留。详见仓库docs/APP_MOTOR_TUNING.md；下文旧版本新增记录是历史。

通过 Noble 直接连接 DJI RS 4 Mini，支持三轴速度、约 1 Hz 的姿态与关节反馈，以及低速关节位置闭环。完整参数、错误码和并发规则见 [API.md](API.md)。

0.7.2 增加自动重连、速度关键帧、逐点定位/停留、保存位置返回、显式四元数数学转换和独立实验协议配置。
自动重连不恢复运动；实验协议未在本机验证。范围见 [能力边界](../docs/CAPABILITIES.md)。
`node examples/expansion-demo.js --help` 只打印帮助，不初始化蓝牙；示例的运动和查询必须现场显式运行。

## 安装

```sh
npm ci
npm test
npm pack --dry-run
```

`npm test` 只用假适配器，不连接硬件。包内包含协议、遥测及生命周期测试。

## 只读连接

```js
import { RS4Mini } from './src/index.js';
const gimbal = new RS4Mini({ deviceId: null, rateHz: 15, ioTimeoutMs: 3000 });
try {
  console.log(await gimbal.connect({ timeoutMs: 30000 }));
  console.log(await gimbal.getAttitude({ fresh: true }));
  console.log(await gimbal.getJointAngles({ fresh: true }));
} finally {
  await gimbal.close();
}
```

安装到其他工程后可从 `rs4mini-sdk` 导入相同 API。每个进程必须重新连接；系统已连接不能代替当前进程的 GATT 句柄。仅缓存 `deviceId`，不缓存句柄。

## 运动

确认稳定器开机、负载平衡且无遮挡后执行。以下代码会移动硬件：

```js
const start = await gimbal.getJointAngles({ fresh: true });
const target = ((start.yaw + 3 + 540) % 360) - 180;
await gimbal.moveTo({ pan: target, toleranceDeg: 1 });
await gimbal.moveTo({ pan: start.yaw });
await gimbal.moveFor({ tilt: 0.05, durationMs: 300 });
```

`setVelocity({pan,tilt,roll})` 为归一化虚拟摇杆输入；缺省轴归零。`setVelocityDeg()` 用 Pan 37.5、Tilt 27.5、Roll 30 度/秒的经验满量程换算，受摇杆设置影响。

`moveTo()` 使用机械关节角：Pan ↔ Yaw，Tilt ↔ Pitch，Roll ↔ Roll。默认容差 1°、总超时 30 秒、单帧超时 3 秒、gain 0.02、minSpeed 0.05、maxSpeed 0.18。已进入容差的轴单独归零。位置环使用已验证的速度协议，不使用未验证的绝对角指令。

## 取消和并发

所有有限运动及其最后停止帧都保有操作所有权；冲突操作以 `RS4MINI_BUSY` 拒绝。手动连续速度可在前一次 `setVelocity()` 返回后更新。新的位置或限时操作会先停止旧连续速度。

```js
const movement = gimbal.moveTo({ pan: target });
const settled = movement.catch(error => {
  if (error.code !== 'RS4MINI_MOVE_CANCELLED') throw error;
});
await gimbal.stop();
await settled;
```

先给运动 promise 安装错误处理，再发起停止，避免应用自己的未处理拒绝。`stop()` 主动唤醒等待和限时睡眠，等待旧运动清理结束；之后的新运动不会被旧操作停止。完成、失败和取消均发送中位停止帧。GATT 帧的 20 字节切片不交错；若某次写入超时或失败，则清理并断开，不再拼接下一帧。

`disconnect()` 可以复用实例，`close()` 永久关闭实例并释放 Noble 运行循环。终止 CLI 时应捕获信号并在 `finally` 使用 `close()`。

## 回调与状态

`onNotification` 是原始块，`onMessage` 是 CRC 校验后的完整 DUML 帧，`onTelemetry` 是解析反馈。回调支持同步或异步函数，异常交给 `onError`；`onError` 自己的异常被隔离。回调和状态读取使用副本，修改副本不改变控制器缓存。

```js
gimbal.onTelemetry = sample => console.log(sample.jointAngles);
gimbal.onError = error => console.error(error);
```

`latestTelemetry` 和 `velocity` 为快照；`activeOperation`、`moveToActive` 用于显示运行状态。姿态角与机械关节角不同，不可互换。反馈内四个浮点值保留为 `orientationQuaternion.components`，坐标约定未验证。

## 硬件示例

- `npm run telemetry:capture`：5/10 秒反馈采样（`RS4MINI_CAPTURE_MS` 配置）。
- `npm run test:neutral`：连接并发送中位停止帧。
- `npm run example:position`：默认 Pan 5° 往返；`RS4MINI_POSITION_AXIS=pan|tilt|roll` 和 `RS4MINI_POSITION_DELTA` 配置轴/幅度。
- `npm run example:full`：包含三轴运动和回中，必须有人在场。
- `npm run telemetry:analyze -- captures/file.log`：离线回放原生抓包。

原始采样和设备缓存由 Git 忽略。0.6.0 修改的硬件验证统一记录在 [实机清单](../docs/HARDWARE_CHECKLIST.md)，当前不要将离线结果称为物理精度验证。

## 分层与前置条件

本版将设备访问与高级运动分为两个模块。应用继续使用原有 `RS4Mini`（原生为 `RSGimbal`）一个入口，
基础操作也通过它访问设备 SDK；不新建第二条连接。底层命令尚未全部解析/验收，在此之前不新增高级功能。
模块映射和限制见 [架构边界](../docs/ARCHITECTURE.md)，命令证据见 [设备命令审计](../docs/SDK_COMMANDS.md)。


0.7.3 新增同一对象的 `appCommands` 参数设备接口，显式来源配置、接口与本机未验收边界见 [API.md](API.md)。全底层命令仍未完成，高级新增暂停。


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


## 0.7.32教程状态被动候选 / 原生0.3.32 build35

显式App来源下tutorialStatus（Python另有tutorial_status，原生appTutorialStatus）与kind=tutorial被动解码04:2B；保留步骤原值、完整32位无符号/有符号状态、9个数值标志、未知位与尾部，以及独立Java位移视图。未知步骤的源回退STEP_FINISH不是完成证明，bit30/31不解释为物理生命周期。缓存复制/不可变、观察者隔离，来源切换/断线清空；不发查询、订阅、ACK或04:2C，不结束查询或moveTo。本机布局/通知、请求关联及物理完成均未验收，完整命令和高级门槛仍false。契约见 docs/APP_TUTORIAL_STATUS.md（仓库根目录）。


## 0.7.33 CENTER只读信息候选 / 原生0.3.33 build36

显式App来源新增getCenterActivationInfo（Python另有get_center_activation_info，原生RSGimbal继承同名selector），要求sourceVersion四种已知格式，无默认/OTHER/协商。固定E5/CENTER-id7、COMMON00:32 GET01/11与严格关联明文ACK；完整本次业务体解析active/date/SN原始值及源signed-decimal字符串、尾部，无旧SN缓存成功回退。GIMBAL04:32同命令号隔离，原生完成后恢复普通04路由；无激活/绑定/SET/FAIL/自动回复/重试/重放或高级新增。见[接口契约](../docs/APP_CENTER_INFO.md)（仓库根目录）。设备/当前版本/布局/激活有效性未验收，全命令及高级门槛false，无硬件/liveUI/厂商执行。

macOS关闭说明（0.7.35）：Noble取消本地CoreBluetooth连接并清理监听器，不额外写入设备拒绝的通知关闭值；其他适配器仍显式unsubscribe。真实断开失败仍报告。实机复测及未通过项见仓库docs/HARDWARE_RETEST_2026-10-20.md。
