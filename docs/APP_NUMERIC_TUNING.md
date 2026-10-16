# 普通跟随/摇杆数值接口（0.7.10 / 原生0.3.10）

应用通过已有RS4Mini/RSGimbal对象的设备SDK使用get/setFollowTuning与get/setRcTuning；显式选择ronin-2.2.2来源配置，复用同一连接、队列、序号与操作协调器。没有新增高级任务、自动切换预设或输入源。

## 范围与接口

| parameter | Follow范围与Pitch/Roll/Yaw索引 | Rc范围与Pitch/Roll/Yaw索引 |
|---|---|---|
| speed | 整数1..100；3 / 12 / 2，size2 | 整数0..100；42 / 43 / 41，size2 |
| acceleration | 整数1..100；15 / 16 / 14，size2 | 不提供 |
| deadZone | 整数0..100；5 / 13 / 4，size2 | 整数0..100；27 / 40 / 26，size1 |
| smoothing | 不提供 | 整数0..30；9 / 39 / 8，size2 |

共18个命名记录。size1为源码INT08U，size2为本组源码INT16U；类型和宽度来自逐项命名证据，不据索引或类型名自动猜测。这些是厂商原始整数，不换算成百分比、度/秒或机械安全范围。

```js
// 只供明确授权的实机会话，默认测试不执行下列硬件调用。
gimbal.appCommands.useProfile('ronin-2.2.2');
const follow = await gimbal.appCommands.getFollowTuning();
const yaw = await gimbal.appCommands.getRcTuning({axis:'yaw'});
const one = await gimbal.appCommands.getFollowTuning({axis:'pitch',parameter:'speed'});
const ack = await gimbal.appCommands.setFollowTuning({axis:'pitch',parameter:'speed',value:20});
```

读取选项axis和parameter可省略；默认读取该组9项，顺序为表中该组参数逐项、每项Pitch/Roll/Yaw。Follow顺序speed/acceleration/deadZone，Rc顺序speed/deadZone/smoothing。轴使用pitch/roll/yaw，不是虚拟摇杆pan/tilt。

写入必须指定axis、parameter和value，只写一项。拒绝布尔、非整数、越界、未知字段、任意index，以及gimbal_create_*或input-source别名。读取/写入的timeoutMs默认3000，范围>0..60000。

## 结果与编解码

读取返回AppParameterReply，附values数组及activePresetVerified:false。每项包含index、size、headerByte、rawHex、axis、parameter、rawValue、withinSourceRange。小端字节34 12解码为4660，ffff保留65535；超出源码输入范围仅标withinSourceRange:false，不截断、不夹取或解释为错误码。

普通命名读取使用04:10，返回码与业务字段分开，第二头字节保留raw，宽度由请求上下文决定。错序、截断、剩余字节或非零返回码拒绝；04:32响应不能满足本组请求。这里和电机数值31/32命令空间分开。

写入使用04:0F，例Pitch跟随speed100为03 02 64 00，Yaw RC deadZone100为1a 01 64。参数验证并复制后先停止主机连续运动，独占操作槽到关联ACK、超时或取消；响应截止时间从停止前置步骤后开始，I/O和清理沿用已有有界机制。没有额外读取、不自动重发、不修改反馈缓存。

成功返回AppCommandReply及axis、parameter、requestedValue、activePresetVerified:false。ACK不代表实机生效或持久化；physicalCompletionVerified仍false。取消不能撤销已发送写入，不承诺回滚或固件原子事务。

## 档位与预设分开

0.7.9的get/setFollowSettings、get/setRcSettings操作custom/low/middle/high档位；本接口操作其普通命名数值。写数值不会自动选择custom档位。

源码继承的Follow Pitch/Yaw setter还检查custom advanced setting profile，该条件依赖App推送的presetID，和两位custom档位不是同一个证明。本SDK目前没有本机活动预设证据，因此仅提供显式来源下的命名寄存器接口，不宣称完整复刻App状态校验或确认数值正在被当前预设采用；读写均返回activePresetVerified:false。

另六个独立配置gimbal_create_*字段与普通RC记录不同，App分支会把input_source=2和数值放在同一请求。本接口不自动选择该分支、不写输入源、不提供这些别名。其型号/UI选择与完整SDK封装仍待完成。

## Python与原生

Python提供相同camelCase方法和get_follow_tuning/set_follow_tuning/get_rc_tuning/set_rc_tuning，使用关键字参数；读取axis/parameter为None表示不筛选，写入要求严格int且拒绝bool。通过app_commands/appCommands访问。

原生RSGimbal继承getFollowTuning:timeoutMs:completion:、getRcTuning:timeoutMs:completion:，首参筛选字典只含axis/parameter，nil或空字典读取全部；setFollowTuning:timeoutMs:completion:、setRcTuning:timeoutMs:completion:的字典必须恰含axis/parameter/value。NSNumber拒绝bool和非有限/非整数值。

Node/Python纯读取可与主机运动共存；原生读取也独占并先停止。四端写入均独占，没有新增调参面板按钮或启动UI。

## 来源与验证

[静态研究](../tools/research/NUMERIC_PARAMS.md) 与 [42方法指纹证据](../protocol/research/ronin-numeric-params-evidence.json) 核对有效继承、枚举命名/缓存映射、普通0F/10缺省模型和INT08U/INT16U打包。三端参数目录由边界检查逐项与18条源码记录对照，Web共享JS实现。

离线检查覆盖混合宽度、小端/无符号异常读值、输入复制、参数与命令隔离、源码范围、操作互斥、畸形响应、非零ACK、取消/超时、无重放、无预设/输入源写入。没有扫描、连接、移动设备、实时UI或厂商代码执行。型号支持、活动预设、真实效果/持久化仍待实机验收，全命令与高级开发门槛仍false。
