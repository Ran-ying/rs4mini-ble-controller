# 部件校准候选请求（SDK0.7.30 / 原生0.3.30 build33）

2026-10-20实机名称确认：用户在重复AUTO00测试时确认，RS4 Mini屏幕将此功能称为“水平校准”。本文历史名“AUTO部件校准”指同一请求；现有API名称保留兼容。两轮收到04:30 COMPLETE100，用户确认完成；设备结果提示需手动确认。该会话名称证据不改变报文不含请求关联ID的边界，也不声称其他型号均同名。

应用仍使用统一高级入口RS4Mini（原生RSGimbal），设备命令通过appCommands封装。显式选择`ronin-2.2.2`来源后，`sendComponentCalibrationRequest({sourcePart:'AUTO'})`发送已定位HG724高级校准入口的04:08/00；这不是原有`sendAutoCalibrationRequest()`的system_calc/index36，也不是6A自动调参或30传感器状态。只有AUTO发送可用，不按完整部件枚举自动开放其他动作。

```js
const gimbal = new RS4Mini();
// 显式连接完成后，由程序主动调用；下面不是自动运行示例。
gimbal.appCommands.useProfile('ronin-2.2.2');
const result = await gimbal.appCommands.sendComponentCalibrationRequest({sourcePart:'AUTO',timeoutMs:3000});
```

Python同名方法及`send_component_calibration_request(sourcePart='AUTO', timeoutMs=3000)`别名；Web共享JS核心；原生`sendComponentCalibrationRequest:timeoutMs:completion:`接收`@{@"sourcePart":@"AUTO"}`。没有新增自动启动行为或面板按钮；本次验证均为假设备/离线，不启动实时UI。

## 电机门槛和事务

输入及显式来源在停止前验证，取得同一操作槽后发送三条速度中位帧。随后04:10读取参数35/宽1，用返回字节的反向bit0判断来源MotorEnabled；禁用时报`RS4MINI_MOTOR_DISABLED`，不发送08，不写0F启用电机，不使用历史缓存、缺省值或调用者传入的“电机已开启”断言。

这个映射已从Ronin2SubscribeIMPL注册MotorEnabled→MOTOR_SPECIAL_CMD，以及Ronin2抽象04:10事件的参数读取/布尔转换/缓存发布核对。源码证据见`protocol/research/ronin-component-motor-gate-evidence.json`和只读`tools/research/ronin_component_motor_gate.py`。它表示App来源的前置条件，不是实时物理电机状态保证；读取与固件校准并非原子操作。

停止阶段完成后，前置读取和08 ACK共用一个timeoutMs预算（>0..60000，默认3000）；已有IO超时独立约束写入。主机操作槽持有至关联ACK或错误清理；冲突、源切换、取消、断线和迟到响应遵循既有事务约束。请求不重发、不保存、不回读、不重连重放。

## ACK与业务状态分别返回

仅未加密ACK、正确会话/序号/端点/命令可以完成等待。返回码非零抛`RS4MINI_DEVICE_ERROR`；加密、缺返回码或坏前置读数返回协议错误。返回码0只表示`acknowledged:true`。

结果包含`requestedSourcePart:'AUTO'`、`motorPreflightRawValue`、`motorPreflightEnabled`、`businessComplete`和独立的`calibration`。ACK业务体至少两字节时，读取part/status，保留全0..255原值、源枚举回退、known标志和尾字节。响应部件与请求不同会报告`responsePartMatchesRequested:false`，不猜同一次物理动作；未满两字节时calibration与部件匹配为null，完整性false，原始bodyHex仍保留，不补PROCESSING。

业务FAIL0、SUCCESS1、PROCESSING2与包层返回码分开。未知业务状态保留raw、known=false，源回退名PROCESSING不是设备仍在校准的证明。完整目录中的部件名称只用于解码，不扩大发送范围或相机功能。

ACK不更新system_calc、自动调参6E、传感器30或其他状态缓存，不触发查询/订阅/自动ACK，不改变姿态/关节反馈。返回即释放主机事务槽，不能推断固件校准已结束；现有30状态也没有本次请求关联证明。

`deviceVerified`、`physicalCompletionVerified`、`modelLayoutVerified`、`motorStatePhysicalVerified`、`businessRequestAssociationVerified`、`firmwareAbortVerified`均false。stop/cancel终止主机等待并发送既有中位帧，不发送假造的固件校准中止。没有新增高级等待/重试/运动组合。

## 验收边界

来源链已分别核对[入口条件](../tools/research/CALIBRATION_ENTRY.md)、[条件传输](../tools/research/CALIBRATION_TRANSPORT.md)、[BLE路由](../tools/research/BLE_ROUTE.md)和[ACK业务偏移](../tools/research/CALIBRATION_ACK.md)。七组跨端向量及事务测试覆盖正常/未知/短响应、禁用/异常/密文前置读、busy、源切换、取消、迟到响应和共享截止时间。

实际会话加密、反射扩展表、固件接受/持续时间/物理完成/中止仍待实机验收，未在用户离家期间操作硬件。本机不能接受时应记录证据，不能自动改用其他部件、其他校准域或加密算法。全命令清单和高级开发门槛仍false。
