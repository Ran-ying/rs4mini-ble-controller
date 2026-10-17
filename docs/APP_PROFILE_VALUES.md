# 源用户配置与工作模式（0.7.19 / 原生0.3.19 build22）

四端统一RS4Mini/RSGimbal入口的设备SDK新增getUserProfile/sendUserProfileRequest、getWorkMode/sendWorkModeRequest；Python有四个snake_case别名，原生对应get...WithTimeoutMs:completion:和send...:timeoutMs:completion:。必须显式ronin-2.2.2来源，共享连接/队列/序号/操作槽，不新增高级任务。

```js
// 只在用户明确授权的配置操作实机会话运行。
gimbal.appCommands.useProfile('ronin-2.2.2');
const profile = await gimbal.appCommands.getUserProfile();
const work = await gimbal.appCommands.getWorkMode();
const ack = await gimbal.appCommands.sendUserProfileRequest({sourceProfileValue:2});
```

| 参数 | 请求/读取域 | 允许写入 | 请求体示例 |
|---|---|---|---|
| userProfile | table_choice，0/size1，源范围0..5 | sourceProfileValue整数0..5 | 2→000102，0→000100 |
| workMode | ronin_gimbal_work_mode，62/size1，源范围0..128 | sourceMode精确Free/Flower/Fpv/Center→0/1/2/3 | Fpv→3e0102 |

getUserProfile/getWorkMode分别以04:10请求单字节00/3e；索引0不是空请求或状态码。保留parameters的headerByte/rawHex以及rawValue、withinSourceRange。配置0/1/2仅对应源UI名M1/M2/M3；3/4/5在源范围内但sourceUiName=null，不推断为FAST/MEDIUM/SLOW。工作模式未知原值如128保留并sourceMode=null，withinSourceRange仍true；255保留、范围false。不回退成先前缓存/默认模式，不按负错误码解释。

配置0、MovementSettingsProfile、04:24推送preset、工作模式62、轴模式34及跟随轴17/18/19/132不是同一枚举或同一状态。源工作名Flower不改译PF/PTF，Fpv也不计为完整FPV跟随切换；SDK不自动改其他域。modelLayoutVerified/activePresetVerified及既有device/physical标志false。源名与源码范围不证明本机支持或当前活动预设。

写入需要显式sourceProfileValue或sourceMode；拒绝布尔、浮点非整数/超范围、未知标签/字段及原始索引/值。工作范围虽0..128，本接口只开放四个已核对命名枚举，不允许任意值128写入。额外配置3..5只是源通用setter允许范围，未确认HG724 UI入口或实际效果。

参数停止前验证/复制，写入先停主机运动，独占至关联04:0F ACK；timeoutMs默认3000，>0..60000。请求前取消不发；已发后取消/超时/断线无重放、回滚、保存或自动回读，重连不重放，NACK直接失败、不缓存兜底成功。结果AppCommandReply加parameter/requestedRawValue及requestedSourceProfileValue或requestedSourceMode，activePresetVerified/persistenceVerified=false。ACK不证明配置激活、固件到位或持久化，不能承诺固件只影响该字段。Node/Python有限查询并发与原生查询占槽/先停差异保留，不自动更新被动缓存。

源审计现41方法，核对HG724继承的setUserProfile/setGimbalWorkMode→通用范围校验→0F，配置事件直接整数、工作事件按枚举value比较与value访问器；没有据未知值推断目标fallback。目录与四种工作枚举跨端比对。离线覆盖零索引/零值、未知读数/错上下文/NACK、输入快照/互斥、取消/超时/断线重连无重放以及Web无Buffer。

没有扫描、连接、移动设备、实时UI、执行厂商代码或新增高级任务。完整模式事务及其他协议、本机效果/活动预设/持久化仍待完成；两项完整性门槛false。
