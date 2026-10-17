# Pitch/Roll微调请求（0.7.14 / 原生0.3.14）

统一RS4Mini/RSGimbal对象下的设备SDK新增sendFineTuneRequest；Python有send_fine_tune_request别名，原生为sendFineTuneRequest:timeoutMs:completion:。必须显式选择ronin-2.2.2协议来源，复用既有连接、序号、队列和操作所有权。它封装原生04:07微调请求，不是moveTo目标、姿态控制闭环或新增高级运动组合。

```js
// 仅供明确授权的实机会话；默认测试不连接硬件。
gimbal.appCommands.useProfile('ronin-2.2.2');
const ack = await gimbal.appCommands.sendFineTuneRequest({axis:'pitch',adjustmentDegrees:-1.29,timeoutMs:3000});
console.log(ack.encodedTenths, ack.nominalAdjustmentDegrees);
```

## 参数与编码

axis仅pitch/roll。源码枚举的ROLL/PITCH/YAW cmd值0/2/4不等于ordinal；目前只确认继承的Pitch/Roll调用方法，不开放Yaw，也不宣称固件不支持Yaw。

adjustmentDegrees必须为有限数-2..2，拒绝布尔、未知轴、任意index/原始字节和未知字段。源码参数先转float32，再float32乘10，然后向零截断为整数、取signed byte低8位。不会按四舍五入或普通double计算替换该过程。

| 输入 | encodedTenths | 两字节体 |
|---|---:|---|
| pitch -1.29 | -12 | f402 |
| roll +1.29 | 12 | 0c00 |
| roll +1.999999999 | 20 | 1400 |
| pitch -0.09 | 0 | 0002 |

requestedAdjustmentDegrees保留请求参数，nominalAdjustmentDegrees为encodedTenths/10的源名义值。它们不是实测角度，不承诺实际移动量、总校准偏差或是否逐次累加；零编码也不擅自当作无效果而省略。源范围不表示机械安全范围或推荐值。

## 请求、停止与响应

参数先验证/复制，再停止主机运动，独占到关联ACK。timeoutMs默认3000，范围>0..60000，使用既有App请求超时与I/O前导清理机制。请求前取消不发04:07；已发后取消/超时只终止主机等待和清理，不重发、不发反向请求或猜测回滚。stop的三帧中位不证明固件微调中止或恢复。

返回AppCommandReply加axis/requestedAdjustmentDegrees/encodedTenths/nominalAdjustmentDegrees。ACK=0仅表示协议响应，额外业务体保持raw；deviceVerified、physicalCompletionVerified和stabilizationStateVerified均false。不修改姿态、关节、04:24或校准缓存，不查询或推断已到位。

## 暂停稳定前置状态

源基类needPauseStabilization初始false，由DataEyeGetPushStabilizationState更新为“turnedOn且notPaused”。Roll方法检查该主机标志，成功回调只转交对象，没有解析实际角度或物理完成。SDK没有目标设备对应状态证据，故不声称该标志为false，也不自动调用DataSingleSendAppStateForStabilization或新增视觉稳定功能。

主机运动槽和中位停止不是DataEye暂停确认。此接口是明确标注的源请求封装，实机前仍需核对固件、模式与前置状态；ACK和源码继承都不能替代本机验收。

## 证据与待验收

tools/research/ronin_controls_trace.py扩展为49方法指纹，包含暂停标志更新/相关暂停方法以及Pitch/Roll成功失败回调；protocol/research/ronin-controls-evidence.json记录源事实。Node/Python/原生轴表逐项比对，Web共享JS；各端黄金向量、可变输入、互斥、错误ACK、请求前后取消和超时离线回归。没有执行厂商代码或操作硬件。

仍需受控验证实际效果/精度/累加/持久化、暂停状态、到位和中止；手柄写入、保存/重置及其他协议继续推进。全部命令与高级新增门槛保持false。


[暂停状态与等待依赖审计](../tools/research/STABILIZATION_DEPENDENCY.md)区分源stabilization状态、3秒等待与真实云台停止/到位；关闭也返回paused、等待不按请求序号关联，未新增运行时功能或声明本机支持。
