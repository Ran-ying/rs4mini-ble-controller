# 恢复设置请求（0.7.16 / 原生0.3.16 build19）

四端统一RS4Mini/RSGimbal入口的设备SDK新增sendFactorySettingsResetRequest；Python有send_factory_settings_reset_request别名，原生sendFactorySettingsResetRequest:timeoutMs:completion:。它是原生04:13源请求封装，不是高级运动组合。

```js
// 只在明确授权的恢复设置实机会话执行；默认离线检查不连接硬件。
gimbal.appCommands.useProfile('ronin-2.2.2');
const ack = await gimbal.appCommands.sendFactorySettingsResetRequest({sourcePlatform:'HG724',timeoutMs:3000});
```

sourcePlatform必填且仅HG724，表示选择已审计的PlatformType.HG724源码分支，不表示已读取本机平台。不能传GimbalComponentType103、其他型号或原始请求体。该分支固定010001三字节、04:13、需ACK；其他平台的空体不适用。单独请求，不附带保存、重启、重新绑定、校准或任何运动程序。

timeoutMs默认3000、范围>0..60000；拒绝未知字段。停止前验证/复制源平台，先停止主机运动，共享既有连接、队列、序号和操作所有权至关联ACK。请求前取消不发13；已发送后取消、超时或断线只表示主机等待失败，不证明固件没有执行/已撤销。不会自动重发、反向回滚、保存或查询。重连只恢复连接，不重放重置。中位停止不等于固件中止恢复设置。

结果AppCommandReply加requestedSourcePlatform='HG724'、targetResetScopeVerified=false、persistenceVerified=false，设备/物理完成标志同样false。ACK0仅表示响应，额外业务体保留，不能宣称已恢复出厂、已重启、已写入非易失存储或全部参数已还原。也不能假设只影响非相机参数；恢复范围尚未证实。NACK直接失败，超时/断线时实际结果未知。

不自动改写本机状态或清零姿态/关节/参数缓存；现有反馈仍按原时间戳/通知更新，连接断开按既有机制清理。调用方后续可显式查询，但读回与物理验收是独立证据。没有跨命令事务或恢复旧配置承诺。

固定APK恢复代码审计现68方法，包括实际HG724分支PC跳转与13号回调：成功只转交对象，失败Ccode转换DJIError，未解析物理完成。三端010001字节与证据逐项比对。离线覆盖精确帧、源分支验证、可变输入、互斥、错命令/NACK、请求前后取消、超时/断线及重连无重放，Web共享JS无Buffer编码。

本批没有扫描、连接、移动设备、执行恢复设置、实时UI或厂商代码执行。实际恢复范围、参数读回、持久化、重启/断连行为与本机接受仍待受控验证。保存04:11、模式/订阅及其他命令仍待继续，全部命令和高级新增门槛保持false。
