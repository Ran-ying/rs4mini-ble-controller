# 外设状态被动源候选（0.7.25 / 原生0.3.25 build28）

显式App来源下四端新增peripheralStatus缓存及kind='peripheral'事件。对应04:66通用源目录46类型、43 getter视图；本机布局/参考系/实际通知未验收。
它与旧rs3研究配置的原始TLV分开，不更新getAttitude/getJointAngles、原生轨迹、告警或运动完成判断。

```js
gimbal.appCommands.useProfile('ronin-2.2.2');
gimbal.onAppStatus = status => {
  if (status.kind === 'peripheral') console.log(status.records);
};
const snapshot = gimbal.appCommands.peripheralStatus;
```

Python为app_commands.peripheral_status，也有camelCase；原生为RSGimbal继承的appPeripheralStatus及appStatusHandler。Web共享JS核心。基础访问仍通过RS4Mini/RSGimbal唯一入口。
没有查询、订阅、ACK、自动控制或新UI操作；需实际消息到达才更新缓存，不自动提高反馈频率。

## 快照与记录

只接受sender4→receiver2、commandSet4/commandId102，flags为有效uint8、ACK位及加密低3位为0的请求型通知。底层沿用CRC/重组校验。
顶层包含kind/profile/commandId/timestamp/bodyHex、rawFlag、sourceRecordBranchSelected、records。
首字节1选择记录分支；其他值保持整个不透明体，records为空，不解释为故障或停止。flag1且无记录也是完整空快照，不填历史值。

每条记录包含rawTag、sourceSignedTag、length、payloadHex、sourceTypes、ambiguous、sourceInt32、sourceViews。
sourceViews逐项保存sourceType/sourceGetter/conversion/value，值为number或boolean。sourceTypes按枚举目录顺序，sourceViews按getter目录顺序；按视图自己的sourceType/sourceGetter关联，不按两数组下标配对。目录含通道、电机功率/温度/角度、陀螺仪/加速度/偏置、ActualPose/TargetPose、源GPS命名及控制状态；名称不证明本机具备该传感器或单位。
未知tag、无getter的类型仍保留原始体，sourceInt32=null、sourceViews=[]；不按名字补字段。

标签21保留YGyroOut与PAcceOut两种源解释，ambiguous=true，分别除10/100，不选一种作为本机量。GPS视图保留源整数除1000000后转double；原始sourceInt32保留，不能把截断值当定位精度。
源三个void方法不生成电流getter，Other255不会与signed map键-1混淆。详见[完整源审计](../tools/research/PERIPHERAL.md)。

长度1/2按源signed byte/short；其他宽度补零尾部到4或取前4个LE字节，8字节窄化的结果同低32位。已存在的长度0记录按源产生0，缺失的记录不产生值。float32舍入顺序和GPS整数截断保留，不改成看似更合理的格式。
重复记录不覆盖前一条，不跨帧合并。signed长度高位>=128或截断拒绝整帧，保留旧缓存；不发布半帧。

## 生命周期和边界

Node/Python返回深拷贝、隔离观察者错误；原生顶层和所有嵌套记录/视图不可变。
切换/重选来源、断线清空缓存。通知不完成查询、不改变运动所有权、不发送自动ACK/订阅，也不改变其他缓存。
所有结果deviceVerified/modelLayoutVerified/referenceFrameVerified/physicalCompletionVerified均false；不能直接用于原生轨迹坐标、急停、到位或电机调参闭环。
源父类可能在派生解析前post，源单例保留旧记录及缺值0行为均未移植。基础表接收条件不代表当前动态扩展表或本机实际报文布局。
六组共享向量覆盖完整目录、碰撞/GPS、全宽度、显式空记录/缺失区分、未知/重复/void、非记录分支。四端仅做离线测试，无硬件/liveUI；全命令和高级门槛仍false。
