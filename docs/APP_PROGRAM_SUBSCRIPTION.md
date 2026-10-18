# 程序状态推送启停请求（0.7.24 / 原生0.3.24 build27）

设备SDK提供显式App来源 `sendProgramStatusSubscriptionRequest`，封装源04:6B的StartContinuePush/StopContinuePush请求。
源枚举、doPack和轨迹界面checkGimbalStateStart/Stop已经静态核对，见[程序研究](../tools/research/PROGRAMS.md)与[工作流](../tools/research/TRACK_WORKFLOW.md)。
此方法发送状态推送启停请求并等待关联ACK；没有建立本机固件接受、远端订阅状态或持续通知的证据。

## API与固定体

```js
gimbal.appCommands.useProfile('ronin-2.2.2');
const startAck = await gimbal.appCommands.sendProgramStatusSubscriptionRequest({
  program: 'track', // track | timelapse | panorama
  enabled: true,
  timeoutMs: 3000,
});
const stopAck = await gimbal.appCommands.sendProgramStatusSubscriptionRequest({
  program: 'track', enabled: false,
});
```

应用通过RS4Mini唯一入口，Web共享JS核心。Python为 `await gimbal.app_commands.send_program_status_subscription_request(program='track', enabled=True, timeoutMs=3000)`，也有camelCase别名。
原生通过RSGimbal继承的 `sendProgramStatusSubscriptionRequest:@{@"program":@"track",@"enabled":@YES} timeoutMs:3000 completion:...`。
program必须命名，enabled必须显式布尔，不接受0/1、原始tag、requestType或其他字段；timeoutMs范围>0..60000。

| program | enabled=true / StartContinuePush=0 | enabled=false / StopContinuePush=1 |
|---|---|---|
| track | 00 00 01 62 | 00 01 01 62 |
| timelapse | 00 00 01 37 | 00 01 01 37 |
| panorama | 00 00 01 63 | 00 01 01 63 |

发送flags=0x40。单次RequestSinglePush=2仍使用独立的[sendProgramStatusRequest](APP_PROGRAM_REQUEST.md)，没有改变其参数或语义。
StopContinuePush是停止状态推送请求；稳定器动作或电机停止由不同命令承担，不混用。

## ACK、被动通知与状态边界

返回只依据当前会话、端点、命令和序号关联的未加密ACK：外层返回码0成功，非0失败，空ACK或加密ACK失败。
bodyHex保留外层返回码后的不透明业务体，允许空体，不按被动6B记录解码。
包含requestedProgram、requestedProgramCommandId、requestedEnabled、requestType及基础ACK字段。
notificationStreamVerified、remoteSubscriptionStateVerified、freshStatusVerified、programCorrelationVerified、modelLayoutVerified、deviceVerified、physicalCompletionVerified均false。

请求型通知始终走独立programStatus缓存/事件，相同序号也不完成ACK等待；ACK不修改该缓存。
停止请求成功后收到的候选通知仍可被动解析，不按本地请求顺序伪造远端订阅开关。
不建立订阅对象、远端活动状态缓存、引用计数、租期/TTL或已完成程序标记；并发请求按自身序号关联，不按最后一次调用归属。
SDK不保证连续推送频率、最后一帧时刻或停止确认，也不把旧缓存当作新通知。

## 生命周期

所有调用是一次有限事务，不自动续订、重复、重试、回读或发送相反请求。源界面的3秒重请求看门狗不移植为SDK后台任务。
本地超时/取消不撤销可能已送达的请求；如需停止状态流，调用方显式发送enabled=false，其ACK仍不是远端停止实证。
断线、重连、切换来源或关闭实例不自动发送启停，也不恢复订阅；源远端停止/租期仍未验收。

Node/Python沿用有限查询，不占运动槽、不发中位前导，可与运动并存；stop和Web blur不取消本请求。
Python任务取消及超时/断线会清理pending；排队超时后不能迟发。原生沿用App独占事务，中位前导、stop取消与失败中位清理保持现有契约。
中位帧是主机摇杆停止，不是固件动作程序停止；取消ACK等待不会发送相反订阅或程序命令。

## 验证与未完成项

六组独立十六进制契约向量由Node/Python/原生共享，测试覆盖输入复制、通知隔离、ACK错误、取消/超时、迟到消息、无隐式相反写入与Web无Buffer路径。
固定源仅离线解析，没有执行厂商代码、扫描、连接、移动设备或运行UI。
本机固件效果、通知流与停止语义、程序执行/取消/完成和全命令覆盖仍待验收；新增高级功能门槛保持false。
