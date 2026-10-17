# 普通跟随轴开关（0.7.18 / 原生0.3.18 build21）

统一RS4Mini/RSGimbal入口的设备SDK新增getSmoothTrackAxes、sendSmoothTrackAxesRequest。Python有snake_case别名；原生getSmoothTrackAxes:timeoutMs:completion:与sendSmoothTrackAxesRequest:timeoutMs:completion:。必须显式ronin-2.2.2来源，复用连接/队列/序号/操作槽，不新增高级任务。

```js
// 仅供用户明确授权的实机会话；离线检查不连接硬件。
gimbal.appCommands.useProfile('ronin-2.2.2');
const before = await gimbal.appCommands.getSmoothTrackAxes();
const ack = await gimbal.appCommands.sendSmoothTrackAxesRequest({axes:{yaw:true,pitch:true,roll:true}});
```

Yaw/Pitch/Roll普通SmoothTrack Enabled分别参数17/18/19，size1、源范围0..1。与132自定义轴位、34轴模式、35电机位、配置/运动预设分开。静态HG724新UI的FPV分支使用DataGimbalSetUserParams数组同包把三项置1；本次bank05 gimbal类扫描未定位逐轴SDK setter，不宣称没有其他动态路径。SDK根据命名元数据和通用0F参数打包提供非空布尔子集，非任意参数或原始值写入；目标实际接受/效果仍未验收。

getSmoothTrackAxes默认读三轴，可用{axis:'pitch'}过滤。请求10的索引按yaw/pitch/roll固定顺序；返回values逐项包含axis/index/size/headerByte/rawHex/rawValue。原值0/1时enabled=false/true，其他值enabled=null、withinSourceRange=false，并保留sourceEnabled=(rawValue===1)的源转换事实。比如3/255不按bit0当true、不填0、不当负错误码。modelLayoutVerified/activePresetVerified与既有设备/物理标志false，不更新被动参数缓存。Node/Python有限查询并发、原生查询占槽且先停的差异保留。

sendSmoothTrackAxesRequest需要axes非空对象，只接受yaw/pitch/roll布尔值，拒绝数字0/1、空对象、未知字段/原始索引。未指定轴在请求体中省略，不补零、不自动读改写；不保证固件其他状态不受影响。按yaw/pitch/roll顺序生成一条0F请求：

| axes | 请求体 |
|---|---|
| {yaw:true,pitch:true,roll:true} | 110101120101130101 |
| {yaw:true,roll:false} | 110101130100 |
| {pitch:false} | 120100 |

参数停止前验证/快照，写入先停主机运动，独占至关联ACK。timeoutMs默认3000、>0..60000。取消前不发，发送后取消/超时/断线不重放、不逐轴重试、不发反向补偿；重连不重放。NACK直接失败，不转缓存成功或自动回读/保存。

返回AppCommandReply加requestedAxes，activePresetVerified/atomicApplicationVerified/persistenceVerified均false。requestedAxes只表示请求，不是逐轴成功状态；ACK0不能证明同包多项原子生效、目标预设活动或持久化。额外响应业务体保留。不会自动写132、34、35或切换UserProfile/输入源，因此三轴全开也不能宣称完成FPV/其他完整跟随模式。

40方法源审计补充三轴读取的比较/真假寄存器常量，目录三端比对。离线覆盖完整/子集/单轴载荷、未知读数/错参数/短体/NACK、快照/互斥、取消/超时/断连重连无重放及Web无Buffer。没有硬件、实时UI或厂商代码执行。仍待本机布局/接受/实际效果/持久化和完整模式事务，两个完整性门槛false。
