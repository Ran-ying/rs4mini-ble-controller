# 手柄命名设置请求（0.7.15 / 原生0.3.15）

统一RS4Mini/RSGimbal入口下新增设备SDK方法sendHandleSettingRequest；Python提供send_handle_setting_request别名，原生sendHandleSettingRequest:timeoutMs:completion:。必须显式选择ronin-2.2.2来源。不是上层运动组合，也不新增相机或手机传感器控制。

```js
// 只在用户明确授权的实机会话中执行。
gimbal.appCommands.useProfile('ronin-2.2.2');
const ack = await gimbal.appCommands.sendHandleSettingRequest({setting:'panDirection',value:1,timeoutMs:3000});
```

| setting | 写入字节 | value | 请求体示例 |
|---|---:|---|---|
| dualChannelMode | 0 | 0/1：源ONE_AXIS/TWO_AXIS | 0→00ffffffffffffff |
| tiltDirection | 1 | 0/1：源布尔反向参数 | 1→ff01ffffffffffff |
| panDirection | 2 | 0/1：源布尔反向参数 | 1→ffff01ffffffffff |

请求04:35、需要关联ACK；每次生成独立8字节体，未指定字节填源新对象默认FF。FF是否意味着不修改对应设置尚未验证；这不是保留其他字段的保证。不能用getHandleSettings读取的8字节全量重写替代源码单字段行为，也不推断profile与table_choice等价。tiltDirection来自PitchOrRollInverse源方法，不能据名字增加独立Roll设置。UNKNOWN255不是本接口允许的写值。

value只接受整数0/1，拒绝布尔、255、NaN、非整数、未知字段和原始索引/字节。timeoutMs默认3000、范围>0..60000。参数在停止前验证并复制，复用原连接、队列、序号和操作槽；先停止主机运动，独占至关联ACK。请求前取消不发送35；请求后取消/超时不重放、不反向回滚，不保证固件撤销写入。其他基础操作和上层组合都走同一入口。

结果为AppCommandReply加setting、requestedValue和unspecifiedByteSemanticsVerified/readbackVerified/persistenceVerified=false。deviceVerified/physicalCompletionVerified同样false。ACK0只是响应；额外业务体保留。不自动填充参数缓存、推断实际状态或发送保存请求。NACK直接报错，不自动回读、不缓存兜底成功、不重试；调用方可另行显式getHandleSettings查询，但该源布局仍待本机验证。

## 与官方上层回调的边界

66方法审计确认源setter使用新对象单字段，避免复用单例残留后两字节。源写入成功回调仅向上转交null；失败回调转DJISDKCache.getValue，对非空结果Class.cast后比较引用身份，可能回报成功，空结果还可能不回调。它不是固件ACK或已证明的BLE回读，本SDK不照搬。源方向读取raw==1而非bit0，模式读取values()[raw]；现有只读API继续原样保留整数，不把异常值当合法开关。

跨端目录与protocol/research/ronin-controls-evidence.json逐项核对；黄金体、非法参数、可变输入、独占、错命令/NACK、取消与超时无重放离线验证。没有扫描/连接/移动硬件、实时UI或执行厂商代码。仍待实机确认FF字段行为、真实模式/方向、持久化和重连后读值；全命令门槛和高级新增门槛仍false。
