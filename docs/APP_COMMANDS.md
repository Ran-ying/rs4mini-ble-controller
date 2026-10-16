# 当前 App 来源的设备参数 SDK（0.7.9 / 原生 0.3.9）

应用继续只创建 `RS4Mini`（原生 `RSGimbal`）。`appCommands` 是该对象的设备 SDK 子接口，复用已有连接、序号、队列、响应关联和操作协调器；没有另开蓝牙连接。高级组合能力没有增加。新接口尚未对设备发送或验收。

## 来源与边界

来源是固定 SHA256 的官方 Ronin 2.2.2/7096 APK 静态恢复视图，复现见 [代码恢复说明](../tools/research/CODE_RESTORATION.md)。HG724 的跟随灵敏度设置链最终发送 `04:0F`、参数 index150/size1，值0/1分别对应 App DEFAULT_MODE/SENSITIVITY_MODE。它不是 PF/PTF/FPV 跟随模式选择，也不是灵敏度百分比。

读取是通用 `04:10` 参数请求，载荷仅含索引；`getFollowSensitivity()` 使用相同外部元数据 index150/size1。没有声称原 setter 会发起该读取，也没有声称本机固件必定支持。

当前 App `CmdIdGimbal.CmdIdType.isNeedCcode()` 返回 true；`RecvPack.setBuffer()` 对响应剥离一个返回码字节。`Ccode.OK` 构造值为0，因此 SDK 在业务解码前检查 BLE 响应首字节：0成功，非0抛出 `RS4MINI_DEVICE_ERROR`，保留 `statusCode`。未知尾部保留 `bodyHex`，不猜错误名称或执行进度。

`04:10` 业务体按显式请求上下文解码：无符号索引、一个原始头字节、按外部 size 提取的原始值。当前 App 跳过第二字节，不能把它断言为宽度；本实现记为 `headerByte`。索引150不能送入旧负 int8 错误解析。按请求次序严格核对索引和长度，重复索引保留；截断、错序和多余字节均拒绝。

## Node 与 Web

以下是显式硬件调用示例，不属于默认测试：

```js
// gimbal 为应用持有且已连接的 RS4Mini
// 选择该配置会清除旧 experimental 配置与缓存；两种来源互斥。
gimbal.appCommands.useProfile('ronin-2.2.2');
const before = await gimbal.appCommands.getFollowSensitivity({ timeoutMs: 3000 });
const ack = await gimbal.appCommands.setFollowSensitivity({ mode: 1, timeoutMs: 3000 });
const after = await gimbal.appCommands.getFollowSensitivity();
```

| 方法 | 契约 |
|---|---|
| `useProfile('ronin-2.2.2')` | 必须显式选择；有操作或查询在进行时拒绝切换 |
| `readParameters({parameters:[{index,size}],timeoutMs?})` | 1..64条；index0..255，size仅1/2/4/8；不接受名字或任意写入 |
| `getFollowSensitivity({timeoutMs?})` | 返回 `rawValue` 和 `mode`；已知0/1，其他值 `mode=null` 并保留原值 |
| `setFollowSensitivity({mode,timeoutMs?})` | mode严格为整数0或1；写入前停止连续速度并独占操作槽，等待关联 ACK；不自动重发 |

响应含 `profile`、`statusCode:0`、`acknowledged:true`、`bodyHex` 和复制的原始 `message`；读取另含 `parameters:[{index,size,headerByte,rawHex}]`。8字节值以十六进制保留精度。所有结果的 `deviceVerified`、`physicalCompletionVerified` 都为 false。写入的 `requestedMode` 记录发送值，ACK 不等于配置已持久化或物理效果已确认。

`timeoutMs` 为大于0且不超过60000的有限毫秒数，默认3000。请求共用现有会话、16位序号分配和端点/命令/响应标志匹配；断连清理请求，迟到响应不能满足新请求。配置写入可被 `stop()`、断连和 Web 失焦取消，错误或取消时完成停止清理后释放操作槽。已发送的配置不承诺回滚，重连不会重放。

读取可与 Node/Python 运动共存，`stop()` 不取消独立读取；断连或读取截止时间会结束它。Web 隐藏/失焦会停止运动与进行中的配置写入。

## Python

`gimbal.appCommands` 与 `gimbal.app_commands` 是同一个对象；支持上述驼峰方法及对应 `use_profile`、`read_parameters`、`get_follow_sensitivity`、`set_follow_sensitivity`。参数为关键字参数；`mode=True` 等布尔值不当作整数接受。await 读取/写入，配置选择为同步方法。未知模式返回 None，原始包为 bytes。异常具有 `.code`，设备拒绝还有 `.statusCode`、`.response`。

```python
gimbal.app_commands.use_profile('ronin-2.2.2')
result = await gimbal.app_commands.get_follow_sensitivity(timeoutMs=3000)
```

## macOS 原生 SDK

方法继承到应用入口 `RSGimbal`：

- `useAppProfile:@"ronin-2.2.2"` 返回 BOOL；有操作/查询时返回 NO。
- `readAppParameters:timeoutMs:completion:`，上下文为 index/size 字典数组。
- `getFollowSensitivityWithTimeoutMs:completion:`。
- `setFollowSensitivity:timeoutMs:completion:`，mode 为 NSNumber。

原生查询与写入都独占操作槽，开始时发送三帧中位停止；这与 Node/Python 的只读并发语义不同。completion 在主队列异步回调，结果/错误二选一，`NSError.userInfo[@"code"]` 提供 SDK 错误码，设备拒绝另含 `statusCode`。未知模式为 NSNull。面板没有新增参数按钮，使用上述程序接口；新行为的 UI/硬件验收均待用户返回。构建不会启动应用或创建测试蓝牙管理器。

## 研究复现与剩余范围

`tools/research/ronin_command_audit.py` 对固定恢复 SHA256 输入产生55类、631个方法的指纹与命令枚举引用。它包括原54类/620方法及 Ccode 11方法，输出 [ronin-command-audit.json](../protocol/research/ronin-command-audit.json)，不包含完整厂商指令体。

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_command_audit.py \
  --dex work/research/code-final/business-05-code-restored.dex \
  --output work/research/reproduced-command-audit.json
```

参数基础不是完整参数 SDK：没有任意参数写入、索引到名称自动映射、跟随模式选择、校准或电机调参。其他已恢复通用命令仍须逐项核对字段、HG724调用分支、回复和通知条件，再封装。系统管理命令与其他代码银行仍未完成审计。`inventoryComplete=false` 和高级开发门槛 false 均保持。


0.7.4 新增两组命名位字段事务，详见 [APP_SETTINGS.md](APP_SETTINGS.md)。这是对继承源码的封装，不是新增PF/PTF预设，也没有任意参数写入或实机证据。


0.7.5 新增无ACK调参请求及04:6E状态，见 [APP_CALIBRATION.md](APP_CALIBRATION.md)。其发送结果不使用参数写入的ACK成功语义，固件完成仍未验证。


0.7.6新增独立31/32空间的命名电机参数，见 [APP_MOTOR_TUNING.md](APP_MOTOR_TUNING.md)。通用参数读取接口保持10空间，不会按相同索引自动命名电机字段。

0.7.7补齐固定命名平衡测试启动与状态/三轴结果读取，完整接口和未验收边界见 [APP_BALANCE_TEST.md](APP_BALANCE_TEST.md)。


## 0.7.8 system_calc自动校准

四端新增独立的普通0F/10/index36固定启动1和状态读取，与6A/6E自动调参分开。读取状态2/3不受写入范围0..1限制，未知值保留raw/null；ACK/报告不代表本次物理完成，取消不保证固件中止，无虚构写零停止。Node108/Web14/Python各86/native75+101+3/research45，类型/边界/构建通过。尚无水平校准身份或本机验收，未操作硬件/UI或新增高级任务。详见 [APP_SYSTEM_CALIBRATION.md](APP_SYSTEM_CALIBRATION.md)。


## 0.7.9 跟随/RC按轴档位

六组参数档位已同步四端，Pitch/Roll/Yaw字段为bits2..3/4..5/6..7，custom/low/middle/high为0/1/2/3；先读后改写，保留其他轴和未知低两位，共用操作槽和总截止时间。Node113/Web14/Python各91/native79+107+3/research49，类型/边界/构建通过；无硬件/UI/高级新增，PF/PTF和custom数值未因此完成。详见 [APP_FOLLOW_MODES.md](APP_FOLLOW_MODES.md)。
