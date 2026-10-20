# 异常与电量被动候选（0.7.21 / 原生0.3.21 build24）

> 0.7.39：abnormal状态保留；battery候选的SDK属性、缓存和事件已移除，仅保留离线codec。见[清理范围](SDK_UNVERIFIED_REMOVAL.md)。

显式ronin-2.2.2来源下，设备SDK被动解释04:27和04:33。应用入口仍只有RS4Mini/RSGimbal，
没有新设备请求、订阅、轮询、自动告警/停机、状态驱动运动或高级任务。

Node/Python/Web通过appCommands.abnormalStatus和batteryStatus读取独立快照；
Python另有app_commands.abnormal_status/battery_status，原生为appAbnormalStatus/appBatteryStatus。
未收到候选时为null/None；getter不等待新帧，timestamp是主机接收时间，不保证实时性。

仅接收sender4→receiver2、commandSet4、请求型且未加密的27/33消息；短帧、ACK、错端点/命令或加密帧不覆盖旧缓存。
27至少5字节，33至少1字节，完整未知位/尾字节保存在bodyHex，不补零、不夹取。
CRC和分片重组沿用设备接收层。

异常对象kind=abnormal，sourceValues包含21个直接源getter和isGimbalLocked复合结果。
后者是Roll/Pitch OR，不含Yaw。getSleepMode来自偏移4的bit0，不能与旧实验来源的休眠字段互换；
getGimbalGravity保留0..3整数，其余数字/布尔类型按源getter保留。完整表见[源码审计](../tools/research/ABNORMAL_BATTERY.md)。
源字段名字包含手机、全景、升级等通用库概念，不能据此认定RS4Mini有对应功能或处于对应状态。

电量对象kind=battery，rawCapacityValue保留0..255，sourceGetter为getCapacityPercentage；
不将255改成错误、未知零值或100，不将此候选自动合入其他型号0D:02电量缓存，也不把它显示为实测百分比。

```js
gimbal.appCommands.useProfile('ronin-2.2.2'); // 真实会话另需用户授权连接
// 本轮只用模拟数据验证，未连接硬件。
gimbal.onAppStatus = status => {
  if (status.kind === 'abnormal') console.log(status.sourceValues);
  if (status.kind === 'battery') console.log(status.rawCapacityValue);
};
const snapshot = gimbal.appCommands.abnormalStatus;
```

onAppStatus/appStatusHandler增加abnormal、battery两种kind。调用方按kind收窄，避免把其他状态当校准/手柄对象。
Node/Python向观察者和getter提供复制快照，原生字典及嵌套sourceValues不可变；观察者异常不会污染缓存。
不覆盖姿态/关节、用户参数、手柄或校准状态，不改变运动所有权，不完成待处理查询。
重选来源、切到旧实验配置或断线均清空两个缓存，不会自动重新订阅或发任何27/33请求。

来源仅为App通用类/其他手持产品的调用，不是HG724布局或本机效果认证。
modelLayoutVerified、deviceVerified、physicalCompletionVerified全false。
本机通知、字段意义/设备兼容和真实UI仍等待用户回家明确要求测试；完整命令与高级新增条件仍未通过。
