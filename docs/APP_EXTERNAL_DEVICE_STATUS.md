# 外设数据被动候选（0.7.27 / 原生0.3.27 build30）

> 0.7.39：本页对应的App来源公开状态入口、缓存和事件已移除。以下仅作历史协议研究；见[清理范围](SDK_UNVERIFIED_REMOVAL.md)。

设备SDK接收04:69的完整业务体，以 `externalDeviceStatus` 暴露独立快照。仅显式选择 `ronin-2.2.2` 来源后生效；这不证明该布局适用于本机RS4Mini。固定源码依据见[外设数据审计](../tools/research/EXTERNAL_DEVICE.md)。

```js
gimbal.appCommands.useProfile('ronin-2.2.2');
const status = gimbal.appCommands.externalDeviceStatus; // null或复制的独立帧
// status.records[n].speedControl?.sourcePitchSpeed 是未确认单位的原始量
```

应用从RS4Mini统一入口调用；Web共享JS核心。Python支持 `gimbal.app_commands.external_device_status` 与camelCase属性；原生RSGimbal继承 `appExternalDeviceStatus`。onAppStatus/原生appStatusHandler收到kind=externalDevice事件，TypeScript的AppStatus联合已同步。没有新增主动请求或UI控制。

## 接收与记录

仅接受sender4→receiver2、commandSet4/commandId105的未加密请求型通知，flags必须uint8且拒绝ACK/encryption位。完整CRC与分包重组沿用既有接收器。至少2字节业务体，从偏移0读取tag/length TLV；length高位即源负长度，拒绝。所有记录和余量必须完整，否则整帧拒绝，保留上一份完整缓存。

每条记录保留rawTag、sourceSignedTag、length、payloadHex。仅tag2产生speedControl：

| 字段 | 语义 |
|---|---|
| rawControlType | 来源原始uint8 |
| sourceControlType | 源CommonStick=1、RockWheel=2、Sensor=3、Other=7；未知也按源返回Other |
| sourceControlTypeKnown | 只有原始1/2/3/7为true，未知不会伪造为7 |
| sourcePitchSpeed/RollSpeed/YawSpeed | 三个signed16LE原始量；单位、轴参考系未验证 |
| trailingHex | tag2前7字节之外的原始尾部 |

未知tag（包括高位负源tag）、重复记录及尾部完整保留，不解释相机字段。tag2载荷不足7字节拒绝，未知tag可为0长度；length上限127。结果还保留bodyHex和本机接收时间timestamp。时间戳不是设备采样时间或新鲜度证明。

## 缓存和操作隔离

快照只含当前帧，不模拟厂商单例的旧速度/控制来源保留，也不复制厂商短包清零副作用。未知记录帧会替换旧快照且不补speedControl；坏帧、ACK或错误端点不会覆盖缓存。Node/Python返回与通知事件均深复制，原生数组及嵌套字典不可变；观察者失败隔离。切换/重新选择来源、断线时清空。

本解析不发送请求、订阅或自动ACK，不完成pending查询，不接管或结束主机运动，不改04:05姿态/关节及其他状态缓存。旧04:66外设状态与本04:69外设数据是不同命令、不同布局和不同缓存；不混用字段。

所有结果deviceVerified、modelLayoutVerified、unitVerified、referenceFrameVerified、physicalCompletionVerified均false。不能把这些sourceSpeed原始数直接交给运动函数作为角速度、目标角或到位判断。没有增加相机、视觉跟踪或高级任务，完整命令和新增高级功能门槛保持false。

## 离线契约

七组共享JSON向量跨Node/Python/原生核对：signed16端点、Pitch/Roll/Yaw顺序、重复记录、Other7与未知255、未知tag和尾部。另测坏TLV/负长度、完整帧替换、深快照与观察者隔离、来源/断线清理、pending查询/运动所有权隔离，以及Web无Buffer。没有实机或实时UI测试。
