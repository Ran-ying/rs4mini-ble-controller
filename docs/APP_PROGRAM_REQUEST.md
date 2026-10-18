# 单次程序状态请求（0.7.23 / 原生0.3.23 build26）

设备SDK增加显式App来源的 `sendProgramStatusRequest`；这是底层查询请求，不是主机动作程序。
固定APK通用类的RequestSinglePush枚举、doPack和接收包层已有静态证据，见[程序研究](../tools/research/PROGRAMS.md)及[接收审计](../tools/research/PROGRAM_RECEIVE.md)。
尚无HG724专属调用、本机固件接受或新通知关联证据。这里只开放固定单次状态请求，不开放程序执行、连续订阅、取消订阅或任意tag。

## API

```js
gimbal.appCommands.useProfile('ronin-2.2.2');
const reply = await gimbal.appCommands.sendProgramStatusRequest({
  program: 'track', // track | timelapse | panorama
  timeoutMs: 3000,
});
console.log(reply.acknowledged, reply.bodyHex);
```

Python使用 `await gimbal.app_commands.send_program_status_request(program='track', timeoutMs=3000)`，camelCase同义方法也支持。
Web共享JS核心；原生通过应用唯一入口RSGimbal继承的 `sendProgramStatusRequest:@{@"program":@"track"} timeoutMs:3000 completion:...`。
原生spec仅允许program键，JS/Python仅允许program和timeoutMs；不能传原始编号或requestType。

| program | 源程序命令 | 04:6B请求体 |
|---|---|---|
| track | 0x62 | 00 02 01 62 |
| timelapse | 0x37 | 00 02 01 37 |
| panorama | 0x63 | 00 02 01 63 |

发送flags=0x40，RequestSinglePush为2；不是枚举ordinal，也不是源默认StartContinuePush=0或StopContinuePush=1。
超时必须大于0且不超过60000毫秒。发送前复制程序选择，后续修改输入不改变请求。

## 返回与通知分离

只等待当前连接、端点、命令及序号关联的ACK。未加密ACK外层返回码0为acknowledged=true，非0失败；空ACK和加密ACK失败。
剥离外层返回码后的bodyHex保持不透明，允许空体，不按6B被动记录布局解释ACK业务体。
返回包含profile、statusCode、acknowledged、bodyHex、原始message及以下字段：

- requestedProgram、requestedProgramCommandId、requestType='RequestSinglePush'。
- freshStatusVerified、programCorrelationVerified、modelLayoutVerified、deviceVerified、physicalCompletionVerified均false。

ACK不证明新通知已到达，不证明程序存在、执行或完成。相同序号的请求型通知不完成查询；被动programStatus缓存和事件沿用[独立接口](APP_PROGRAM_STATUS.md)。
本方法不读取旧缓存兜底，不等待下一次通知，不把ACK写入该缓存，不自动发送通知ACK。

## 生命周期与各端差异

Node/Python沿用有限查询：不占主机运动槽、不先发中位停止，可与运动并存。stop只取消运动，不取消此类有限查询；Web blur沿用stop，因此该请求仍等待自身截止时间或断线。
Python任务取消会移除pending；Node/Python超时、断线及迟到ACK均不会重放请求。排队超时后不能迟发。
原生沿用App独占事务：先发送三帧中位停止，占槽至ACK/失败；stop可取消请求，超时/取消可能发送中位清理。
这些中位帧是主机摇杆停止，不是固件动作程序停止。四端均不自动重试、订阅回退、重新连接后恢复请求或发送程序执行命令。

本功能离线验证使用合成消息、假设备/GATT和源码证据，不扫描、连接或移动硬件。
全部命令枚举与实机验收仍未完成，新增高级功能门槛保持false。

0.7.24另提供[显式推送启停请求](APP_PROGRAM_SUBSCRIPTION.md)，本单次方法仍固定type2；其通知与ACK分离契约不变。
