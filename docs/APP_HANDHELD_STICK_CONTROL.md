# 手柄摇杆控制开关候选（SDK0.7.31 / 原生0.3.31 build34）

应用仍使用统一高级入口RS4Mini（原生RSGimbal）。设备SDK在显式`ronin-2.2.2`来源下新增：

```js
gimbal.appCommands.useProfile('ronin-2.2.2');
const result = await gimbal.appCommands.sendHandheldStickControlRequest({enabled:false,timeoutMs:3000});
```

连接完成后由程序主动调用；不会在连接、切换来源或重连时自动发送。Python同名方法及`send_handheld_stick_control_request(enabled=False,timeoutMs=3000)`别名；Web使用共享JS核心；原生`sendHandheldStickControlRequest:timeoutMs:completion:`接收`@{@"enabled":@NO}`。没有新增面板按钮或实时UI操作。

## 来源和范围

[HG724工厂/键/Setter审计](../tools/research/HANDHELD_BINDING.md)确认条件PlatformType.HG724选择Mobile手柄抽象，实际Setter键为StickGimbalControlEnabled，并调用04:58布尔类。原方法名称含MicroPhones，不能据此创建麦克风或相机接口。

请求是APP/id0→GIMBAL/id0，04:58、单字节false00/true01、flags40。它不是04:35的手柄设置、0F/10中的摇杆速度/死区，也不是04:57被动状态订阅。源码有条件型号链，实际固件的开关效果、虚拟摇杆受影响方式和持久化仍未验收。

## 事务与响应

必须显式传boolean enabled，拒绝数字0/1、字符串、缺失值与未知选项。输入及来源在停止前验证，复制请求快照；取得操作槽后发送三条既有速度中位帧，再发送一次58并持有至关联ACK或错误清理。timeoutMs范围>0..60000、默认3000，响应等待在停止后开始，已有IO超时独立约束传输。

仅同一会话、正确序号/端点/命令且未加密的ACK可以完成请求。返回码0得到acknowledged=true；非零为RS4MINI_DEVICE_ERROR；空ACK或密文为协议错误。额外ACK业务体只保留bodyHex和原始message，不猜成“实际开关状态”。

结果另含sourceSetting=StickGimbalControlEnabled和requestedEnabled。以下字段均false：deviceVerified、physicalCompletionVerified、modelLayoutVerified、readbackVerified、persistenceVerified、notificationAssociationVerified。requestedEnabled只表示请求快照，不是设备回读。

ACK不更新handheldStickStatus，不触发57订阅/查询，不改变姿态或关节反馈。真实57通知可照常更新其独立缓存，但不能代替58的ACK，也未证明与本次设置关联。主机运动互斥只保护请求事务，ACK不提供固件执行或运动完成保证。

停止、取消、断线或超时后不重发，不发反向58回滚，重连不恢复设置。已经写出的请求可能已被固件处理；取消主机等待不能当作设备撤销成功。没有自动接管摇杆、按键映射或高级运动组合。

## 验收

三组跨端共享向量覆盖false、true和不透明ACK尾部；专项回归覆盖来源/参数验证、快照、busy/来源切换、错误序号/端点/ACK位、真实57与等待隔离、NACK/密文/坏包、取消前后及超时无重放。Web另验证无Buffer路径，原生使用假设备。

本次没有扫描、连接、写入实际稳定器、启动实时UI或执行厂商代码。实际会话加密、现场型号/注册、设备接受、状态含义、持久化和控制交互等待实机验收；所有命令覆盖和新增高级功能门槛仍false。
