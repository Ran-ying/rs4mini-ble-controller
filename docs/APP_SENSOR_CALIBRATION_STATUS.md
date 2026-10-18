# 传感器校准被动候选（0.7.28 / 原生0.3.28 build31）

设备SDK增加显式当前App来源的sensorCalibrationStatus与kind=sensorCalibration事件，只解析接收到的04:30完整业务体。固定类绑定和枚举依据见[校准域研究](../tools/research/SENSOR_CALIBRATION.md)。这不证明本机RS4Mini固件采用该布局。

```js
gimbal.appCommands.useProfile('ronin-2.2.2');
const status = gimbal.appCommands.sensorCalibrationStatus; // null或复制的状态
// status.rawProgressValue/status.rawStatus 保留原始字节
```

应用仍从RS4Mini统一入口访问。Web共享JS核心；Python为 `gimbal.app_commands.sensor_calibration_status`，同时提供camelCase；原生RSGimbal继承appSensorCalibrationStatus，通过appStatusHandler接收不可变字典。Node/Python的onAppStatus事件与TypeScript AppStatus联合已同步，没有新增面板控制或校准触发按钮。

## 解析范围

只接受sender4→receiver2、commandSet4/commandId48的未加密请求型通知，flags为uint8，拒绝ACK和加密位。CRC和分包重组沿用既有接收器。载荷至少两字节，否则拒绝且保留上一份完整缓存；不复制源短包的进度0/状态OTHER默认值。

| 字段 | 含义 |
|---|---|
| rawProgressValue | 载荷0的完整uint8，0..255保留，不截断到100 |
| rawStatus | 载荷1的完整uint8 |
| sourceStatus | 源COMPLETE=0、PROCESSING=1、FAIL=3、OTHER=9；未知回退OTHER |
| sourceStatusKnown | 原始0/1/3/9为true；如2/255为false |
| bodyHex / trailingHex | 完整业务体 / 第2字节之后的原始尾部 |
| timestamp | 主机收到并解码的时间，不是设备采样时间或请求关联 |

FAIL源值3不是ordinal2。状态不能按非零统一转为inProgress=true，也不能复用04:08的FAIL0/SUCCESS1/PROCESSING2。另一个名称近似AutoCalibrationStatus类没有绑定在本基础表04:30位置，其getter/变化检测不用于本接口。

COMPLETE只是本帧源状态名称。所有结果deviceVerified、modelLayoutVerified、progressUnitVerified、requestAssociationVerified、physicalCompletionVerified均false。不提供percent/inProgress、到位或固件校准结束承诺，也不推断与某次请求相关。

## 独立缓存和生命周期

当前帧独立快照、未知值与尾字节保留。Node/Python的getter与事件对象均复制，并隔离同步/异步观察者失败；原生字典不可变，捕获同步回调异常。短包、ACK、加密或错误端点不覆盖已有缓存；重新选择/切换来源或断线清空。

本解析不发送查询、订阅或自动ACK，不结束pending查询或主机运动，不改变04:05姿态/关节，不填充6E calibrationStatus、system_calc读取、平衡测试或其他状态缓存。sourceStatus=COMPLETE也不会触发停止或运动完成。

旧other-model实验配置保留其独立格式；来源互斥，当前App候选不套用旧inProgress布尔，也不修改旧配置。04:08触发仍未开放；30源类start为空，不新增空体查询。

## 验证与未完成项

七组共享JSON向量跨Node/Python/原生一致；测试覆盖全部uint8值、FAIL3/未知2、OTHER9/未知255、进度255、尾部、短/ACK/加密拒绝、快照与观察者隔离、来源/断线清理、COMPLETE不结束查询或运动、Web无Buffer。

尚需本机布局、实际扩展分发、进度单位、型号UI路径、请求关联、校准效果和中止实机证据。没有扫描/连接/移动或校准设备，没有实时UI/厂商执行、相机/视觉/高级功能新增。完整命令与新增高级开发门槛保持false。
