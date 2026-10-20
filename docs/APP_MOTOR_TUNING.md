# 命名电机数值参数（0.7.36 / 原生0.3.37）

应用仍只创建 `RS4Mini` / `RSGimbal`，通过设备 SDK 复用同一个连接、队列和操作槽。接口要求显式 `ronin-2.2.2` 来源配置，本次只做读取，不触发调参或高级运动。

## 命令空间与来源

当前 App 的 `DJIGimbalRonin2Abstraction` 十二个 setter 由 HG702/HG724 继承，调用 `setRonin2MotorParam()`，再调用 `DataGimbalRoninSetUserParams` 的 `04:31`。读写按名字查 `DJIGimbalParamInfoManager`，已确认加载的资源是 `gimbal_param_infos/res/DB.json`。BaseCommand 的这十二个键指定 `DataGimbalRoninGetUserParams/04:32` 作为读取类。

它和 `04:0F/10` 用户参数是不同命令空间。资源内 index0 同时存在 table_choice 和 ronin_sensibility_pitch，不能只凭线上索引反查名字；本接口从源码命名键和请求上下文映射字段。没有根据 Ronin2 类名选择另一份参数资源。

| parameter | Pitch / Roll / Yaw 索引 | 源码输入范围 |
|---|---|---|
| `stiffness` | 0 / 1 / 2 | 整数5..100 |
| `strength` | 3 / 4 / 5 | 整数1..100 |
| `gyroFiltering` | 6 / 7 / 8 | 整数0..100 |
| `preControl` | 9 / 10 / 11 | 整数0..100 |

这些是厂商原始数值；不换算成角度、速度、百分比或物理增益。范围用于拒绝超出源码的请求，不能视为机械安全范围或负载推荐值。继承路径不证明每个固件或 App UI 都启用了这些字段。

## Node

```js
// gimbal 为应用已有且已连接的对象；以下调用会访问硬件，不属于默认离线测试。
gimbal.appCommands.useProfile('ronin-2.2.2');
const all = await gimbal.appCommands.getMotorTuning();
const yaw = await gimbal.appCommands.getMotorTuning({ axis: 'yaw' });
const one = await gimbal.appCommands.getMotorTuning({ axis: 'roll', parameter: 'stiffness' });
const ack = await gimbal.appCommands.setMotorTuning({ axis: 'roll', parameter: 'stiffness', value: 50 });
```

`getMotorTuning({axis?,parameter?,timeoutMs?})` 默认读取12项，可按一个轴或一种参数筛选。轴使用源码 `pitch/roll/yaw` 命名，和虚拟摇杆 `pan/tilt` 选项分开。单项返回 AppParameterReply 加 `readMode:'single'`；多项逐项读取完成后返回非原子汇总（下述契约），均含 `values` 数组，每项为：

```js
{ axis:'roll', parameter:'stiffness', index:1, size:1,
  headerByte:1, rawHex:'32', rawValue:50, withinSourceRange:true }
```

选择顺序为上表逐行、每行Pitch/Roll/Yaw；不依赖返回索引自动猜字段。未知数值如255保留原值和十六进制，`withinSourceRange:false`；不夹取、不填入默认值。

多项读取每次只发送一个索引并等待严格关联的04:32 ACK，依选定顺序完成后返回：

```js
{ profile:'ronin-2.2.2', deviceVerified:false, physicalCompletionVerified:false,
  readMode:'sequential', atomic:false, values:[/*全部所选值*/],
  parameters:[/*全部已验证记录*/], replies:[/*每次真实单项响应，含message/bodyHex*/] }
```

不合成顶层ACK、message、bodyHex或statusCode。这个结果不是同一时刻快照；前后参数可能在读取期间变化。任何一项失败、超时、取消或断线均整体拒绝，无部分成功、默认补值、重发或断线重放。timeoutMs是整个读取循环共用的总预算，不能每项重新获得完整超时。多项在前置停止后独占操作槽到完成/错误；Node/Python单项保留原有限查询语义，原生继续独占且先停止主机运动。

三端实机已通过默认12项、按轴4项、按参数3项及单项1项，SDK只发原已验证的单项请求。历史多索引一次请求只收到首条，当前不再发送该形式。

`setMotorTuning({axis,parameter,value,timeoutMs?})` 每次写一项，拒绝其他名字、任意索引、布尔/浮点值和越界值。参数先验证并复制，再停止主机连续运动并取得操作槽，发送 `04:31`、等待关联的状态 ACK。成功返回 AppCommandReply，加 `axis/parameter/requestedValue`；不把请求值写入反馈缓存，不自动重发。

`timeoutMs` 默认3000，范围大于0且不超过60000ms；写操作的响应截止时间从停止前置步骤之后开始，I/O和清理沿用已有截止时间。单项读取可与Node/Python运动共存，多项独占；写入独占，支持stop/断连取消。已发送的值不承诺回滚或持久化。ACK和源码范围均不能代替写后回读与实际效果验收，结果仍为 `deviceVerified:false`、`physicalCompletionVerified:false`。

## Python 与原生

Python提供相同 camelCase 方法，以及 `get_motor_tuning()`、`set_motor_tuning()`；参数为关键字参数，读取轴/参数默认None表示不筛选。通过同一个 `gimbal.app_commands` / `gimbal.appCommands` 对象访问。

原生 `RSGimbal` 继承：

- `getMotorTuning:timeoutMs:completion:`：筛选字典只接受axis/parameter，空字典或nil读取全部。
- `setMotorTuning:timeoutMs:completion:`：字典须含axis/parameter/value，数值拒绝布尔NSNumber。

原生查询/写入均独占操作槽并先发送中位停止，completion沿用主队列异步回调；详细差异与错误码见 [APP_COMMANDS.md](APP_COMMANDS.md)。面板删除两项已退役查询，仍提供单项电机表单；本次只实测无GUI SDK，未做实时UI验收。

## 编解码与复现

读取请求每次只含一个索引，如Yaw依次发 `02`、`05`、`08`、`0b`；写Roll刚度50为 `01 01 32`，命令31，flags40。查询响应先分离Ccode；业务体按请求上下文读取“索引、原始头字节、外部宽度指定的原始值”，第二头字节保持raw，不假定它等于宽度。截断、错序、尾部剩余或非0返回码均拒绝。查询命令32不能被同序号的命令10响应满足。

当前记录全部为typeID0/INT08U、size1。已核对枚举、合成switch映射、单项/数组两条doPack分支、Number.intValue和BytesUtil.getBytes(int)低字节在前的实现，不只根据资源宽度猜写入载荷。

[ronin-motor-evidence.json](../protocol/research/ronin-motor-evidence.json) 包含12条按名字确定的记录和26个方法指纹，保留源范围不是机械安全保证的事实。复现：

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_motor_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --dex work/research/code-final/business-05-code-restored.dex \
  --output work/research/reproduced-motor-evidence.json
```

工具校验固定APK/恢复视图哈希、命名构造、唯一名称、类型/宽度/范围、setter派发及数值打包分支；不执行厂商代码、不分发完整资源或指令体。SDK仅开放这12项的单项写入，没有任意参数写接口或主机批量预设任务。实机接受/生效/持久化、负载适用性、平衡测试、水平校准及其余命令仍待验收，完整性与高级开发门槛保持false。
