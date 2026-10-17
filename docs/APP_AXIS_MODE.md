# 轴模式命名读写（0.7.17 / 原生0.3.17 build20）

四端统一RS4Mini/RSGimbal入口的设备SDK新增getAxisMode、sendAxisModeRequest，Python有get_axis_mode/send_axis_mode_request别名，原生getAxisModeWithTimeoutMs:completion:及sendAxisModeRequest:timeoutMs:completion:。必须显式选择ronin-2.2.2来源；共享连接、队列、序号和操作所有权，不新增高级运动组合。

```js
// 仅在用户明确授权的实机会话运行。
gimbal.appCommands.useProfile('ronin-2.2.2');
const before = await gimbal.appCommands.getAxisMode();
const ack = await gimbal.appCommands.sendAxisModeRequest({sourceMode:'ThreeDRoll360',timeoutMs:3000});
```

| sourceMode | 源枚举value | 写入34的整字节 | 0F请求体 |
|---|---:|---:|---|
| ThreeAxis | 0 | 0 | 220100 |
| TwoAxis | 1 | 8 | 220108 |
| Roll360 | 2 | 16 | 220110 |
| ThreeDRoll360 | 3 | 24 | 220118 |

四种是源码通用继承setter接受的轴模式枚举；HG724新UI只定位到ThreeAxis/ThreeDRoll360入口，不据另外两项宣称本机支持。不是PF/PTF/FPV列表位置，也不是参数35的motor.roll360位64。sourceMode只接受上述精确命名，拒绝数字、布尔、未知字段/原始索引/值。

getAxisMode以04:10请求索引34、宽度1。原始字节保留，按已审计源事件读取(raw>>3)&3映射sourceMode/sourceModeValue；unknownBits=raw&0xe7，保留返回记录headerByte。即使raw=255仍保留原值、模式源名及231未知位，不按负错误码、无效值或可写原值解释。modelLayoutVerified/activePresetVerified以及既有设备/物理验证标志false，不填04:24缓存。Node/Python查询沿用既有有限查询并发规则；原生查询占槽且先停止主机运动。

sendAxisModeRequest按源setter将枚举value左移3后直接写完整字节，不先读改写34，不宣称保留其他位；otherBitsPreservationVerified=false。不会自动读写132、17/18/19、预设、输入源、电机35或保存参数，也不触发任何运动程序。它不是完整3D Roll360/FPV/Custom切换事务。

参数停止前验证并复制；写入先停止主机运动，独占至关联04:0F ACK。timeoutMs默认3000、范围>0..60000。请求前取消不写，发送后取消/超时/断线不重放、不反向回滚；重连不重放。NACK直接失败，不转缓存成功。结果AppCommandReply加requestedSourceMode/requestedRawValue、activePresetVerified/otherBitsPreservationVerified/persistenceVerified=false。ACK不是物理到位、活动预设或持久化证据。

40方法审计补充源事件FLOWER_SPECIAL_CMD读取的右移3/掩码3；三端枚举目录逐项比对。离线覆盖四种请求体、未知位、短体/错误上下文/NACK、可变输入、互斥、取消、超时、断连重连无重放和Web无Buffer。没有扫描/连接/移动设备、实时UI、厂商代码执行或高级新增。

仍需本机核对模式布局/接受/物理行为、其他位影响、预设条件和持久化；完整模式事务及其他协议继续推进。全部命令和高级新增门槛保持false。
