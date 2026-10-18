# 程序状态被动候选（0.7.22 / 原生0.3.22 build25）

显式`ronin-2.2.2`来源下，设备SDK被动解释未加密请求型04:38、04:64、04:6B。
应用仍通过RS4Mini/RSGimbal统一入口。没有程序启动/停止、查询、订阅、轮询、自动ACK、相机控制或高级任务新增。

Node/Python/Web为`appCommands.programStatus`，Python另有`app_commands.program_status`；原生为`appProgramStatus`。
未收到完整候选前返回null/None，读取getter不会等待或发送。onAppStatus/appStatusHandler增加`kind='program'`，调用方须按kind收窄。
timestamp是主机收到消息的时间，不保证设备实时性。

```js
gimbal.appCommands.useProfile('ronin-2.2.2');
gimbal.onAppStatus = status => {
  if (status.kind === 'program') console.log(status.format, status.sourceValues, status.records);
};
const snapshot = gimbal.appCommands.programStatus;
```

## 格式

| commandId | format | sourceValues |
|---|---|---|
| 56 / 0x38 | standalone-timelapse | rawFlags、status=rawFlags&3、takingOrPreview、finishedPoints、currentRoadPercent、totalRoadPercent、unknownFlagBits |
| 100 / 0x64 | standalone-panorama | status原值、currentPictures/totalPictures两个uint16 LE |
| 107 / 0x6B | program-records | 顶层为null，内容逐条存入records |

standalone至少4/5字节，保留完整bodyHex及未知尾字节，不将计数夹取为百分比或解释为到位。
6B的rawSuccessByte保留原值：0或1时sourceSuccess=true，其他值false且后续体保持不透明；这个业务标志不是外层ACK返回码。
ACK消息在本接口入口就拒绝，不尝试对其剥离返回码；原始payload与业务体区别见[接收审计](../tools/research/PROGRAM_RECEIVE.md)。

6B每条记录包含rawTag、sourceSignedTag、length、payloadHex和sourceValues：

- tag62：status、finishedPoints、currentPercent、totalPercent，至少4字节。
- tag37：rawFlags、status=rawFlags&7、recordingOrPreview、finishedPoints、currentRoadPercent、totalRoadPercent、unknownFlagBits，至少4字节。
- tag63：status及两个uint16 LE计数，至少5字节。
- 其他tag：sourceValues=null，完整记录保留。重复tag仍是多条记录，不覆盖前条。

独立38的状态掩码3与6B内37的掩码7不同；状态原值（包括0、4、255）不会被转换成运动完成。
长度必须完整、有符号源长度的高位>=128被拒绝；已知记录不能跨记录读取字段。在sourceSuccess=true的记录解析中，任何坏记录拒绝整帧，保留旧缓存。
源success为0/1但没有完整记录头的短体也拒绝，不把源旧单例残留字段填成新状态。

## 缓存、事件与发送边界

仅接受sender4→receiver2、commandSet4、命令38/64/6B且flags ACK位为0、加密位为0的消息。
底层沿用CRC校验与分片重组；错端点、ACK、加密、短帧及截断TLV不覆盖缓存。
可以观察请求ACK的通知，但SDK不会自动发送ACK。源38/64类会回复ACK，这一行为本轮没有移植，实际通知流仍待实机验收。

缓存只存最后一条完整候选帧，不跨帧合并不同程序记录，也不从源共享单例继承旧字段。
Node/Python的getter和观察者收到各自复制快照；原生顶层、records及嵌套字典不可变。
重选来源、切换到其他实验配置或断线清空缓存；没有自动恢复订阅或运动。
通知不改变运动所有权、不完成待处理查询、不更新姿态/关节、校准、电量或其他独立缓存。
观察者抛错不污染快照或中断接收流程。

所有候选都有deviceVerified/modelLayoutVerified/programCorrelationVerified/physicalCompletionVerified=false。
这些只说明所选App通用源布局可解析，不证明本机实际通知、型号/扩展表、物理动作或停止效果。
源码的ACK后UI状态、3秒重订阅和1200ms解锁都没有作为SDK到位/停止判断，见[工作流审计](../tools/research/TRACK_WORKFLOW.md)。

Node/Python/原生共用5组独立JSON测试向量，Web通过相同JS核心及无Buffer测试验证。
硬件、真实UI及实际自动ACK需求未验收，完整命令和高级新增门槛保持false。

0.7.23另增[显式单次请求](APP_PROGRAM_REQUEST.md)，本被动接口的通知/缓存语义与无自动发送行为不变。
