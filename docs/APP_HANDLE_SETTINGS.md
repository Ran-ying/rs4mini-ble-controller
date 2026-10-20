# 手柄参数只读查询（0.7.13 / 原生0.3.13）

> 0.7.36范围更新：主动getHandleSettings/queryCalibrationStatus及三端等价入口已按用户要求移除。以下主动查询描述保留为历史研究，当前不可调用；被动calibrationStatus进度、自动调参开始/停止请求及其他独立接口保留。

统一RS4Mini/RSGimbal对象下的设备SDK提供getHandleSettings({timeoutMs})，Python另有get_handle_settings(timeoutMs=...)；原生为getHandleSettingsWithTimeoutMs:completion:。必须显式选择ronin-2.2.2来源配置，复用原连接/序号/队列。没有手柄写入、参数保存/重置或相机控制接口新增。

```js
// 仅供已授权的硬件会话；默认测试不会连接设备。
gimbal.appCommands.useProfile('ronin-2.2.2');
const result = await gimbal.appCommands.getHandleSettings({timeoutMs:3000});
console.log(result.values, result.bodyHex);
```

04:36请求体为空，要求关联ACK；返回码非0抛设备错误，去掉返回码后至少8字节才解码，短体不补零。values每项包含sourceGetter、offset、size1、rawValue、sourceBit0。源字段顺序如下：

| offset | sourceGetter | sourceBit0 |
|---|---|---|
| 0 | getDualChannelEnable | null，保留完整原值 |
| 1 | getTiltDirection | null |
| 2 | getPanDirection | null |
| 3 | getProfile | null，不映射其他预设 |
| 4 | getPitchFree | null |
| 5 | getZoom2SpeedEnable | bool，原值仍保留 |
| 6 | getRotationFocusEnable | bool，原值仍保留 |
| 7 | getCellphoneSensorDisable | bool，原值仍保留 |

例如业务体070100ff030203fe63保留首字节7、profile255、尾部99；bit0只用于后三个源布尔getter，字节2为false、3为true。后三项为协议原值记录，不提供镜头或手机控制。handle的getProfile不是table_choice/UserProfile或04:24 MovementSettingsProfile，未据名称推断等价关系。

返回继承AppCommandReply：profile是协议来源ronin-2.2.2、bodyHex保留完整业务体/尾字节、message为复制的原始响应，deviceVerified、physicalCompletionVerified及modelLayoutVerified均false。ACK=0只表示收到关联协议响应，不确认本机布局、设置有效或持久化。请求结果不填入04:24被动缓存或校准状态。

timeoutMs默认3000，范围>0..60000。配置/参数先验证，超时/断线清理待处理查询，无自动重发。断开连接仍执行已有三帧中位停止，不写04:35/11/13。Node/Python有限查询可与运动共存；原生查询占用操作槽并先停止，与既有查询语义一致。

来源、8个getter和继承解析固定在protocol/research/ronin-controls-evidence.json与tools/research/FINE_HANDLE_RESET.md；三端目录逐项比对，Web共享JS。HG724继承方法可读不等于固件/UI支持。仍须受控实机确认04:36响应、实际字段、错误与并发；本轮没有扫描、连接或硬件操作。微调、手柄写入、保存/重置和全部命令仍未完成，两项完整性门槛保持false。
