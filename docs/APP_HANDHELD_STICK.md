# 手柄状态被动候选（0.7.20 / 原生0.3.20 build23）

显式ronin-2.2.2配置下，设备SDK被动解释04:57。应用仍只使用RS4Mini/RSGimbal高级入口。
Node/Python/Web读appCommands.handheldStickStatus，Python另有app_commands.handheld_stick_status；
原生读appHandheldStickStatus。没有主动查询、订阅或04:58发送，没有新高级动作或UI控制。

只接收sender4→receiver2、commandSet4、commandId57（十六进制）、请求型且未加密帧。
已知布局至少6字节；短帧、ACK、错误端点或加密帧不覆盖缓存。额外字节全部保留在bodyHex。
CRC/分片重组沿用既有设备接收层。

| 属性 | 内容 |
|---|---|
| kind / profile / timestamp | handheldStick / ronin-2.2.2 / 主机接收时间 |
| sourceStickX / sourceStickY | 偏移0/2的signed int16 LE源值 |
| rawStateWord | 偏移4的uint16 LE原始字 |
| sourceTriggerPressed | 状态字bit0 |
| sourceStickControlEnabled | 状态字bit1 |
| unknownStateBits | 状态字 &0xfffc，保留其余位 |
| bodyHex | 完整源体，包括额外/未知字节 |

没有把X/Y命名为Pan/Tilt，不归一化、不夹取、不假定中心1024或正负方向。
字段来自App通用MobileHandheldController消费路径，未建立HG724型号布局，因此
modelLayoutVerified、deviceVerified、axisMappingVerified、physicalCompletionVerified均false。
不把其他产品的源状态当本机实时手柄状态或运动完成。

```js
// 仅供用户明确授权的硬件会话；本轮只用模拟数据验证。
gimbal.appCommands.useProfile('ronin-2.2.2');
gimbal.onAppStatus = status => {
  if (status.kind === 'handheldStick') console.log(status.sourceStickX, status.rawStateWord);
};
const snapshot = gimbal.appCommands.handheldStickStatus; // null或候选快照；不等待新帧
```

onAppStatus增加handheldStick分支，原生使用既有appStatusHandler；调用方按kind收窄。
Node/Python观察者与getter返回复制值，原生返回不可变标量/字符串字典。观察者异常不破坏缓存。
通知不改变姿态/关节、固定参数或校准缓存，不创建/释放运动所有权，不完成待处理查询。
重选来源、切换旧研究来源或断线会清空快照，没有消息时保持null，不伪造零值或发送请求。

04:58仅恢复通用一字节bool编码和ACK路径，六段调用只见MobileHandheldController，
没有HG724接受、作用、可恢复性或持久化证据，SDK继续不开放发送。
相关源方法名不能用来增加麦克风、相机或其他功能。

源码证据见[手柄协议审计](../tools/research/HANDHELD_STICK.md)。本机须在用户回家明确要求测试后，
核对固件、真实57帧、状态位与实际操作；当前没有硬件或实时UI验收。全部命令及高级新增门槛仍false。


0.7.31另提供[显式手柄开关请求](APP_HANDHELD_STICK_CONTROL.md)，ACK不更新本页57被动缓存，也没有自动订阅或请求关联证明。
