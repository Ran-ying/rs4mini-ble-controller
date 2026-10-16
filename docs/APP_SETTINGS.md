# 命名位字段设备 SDK（0.7.4 / 原生 0.3.4）

在同一个应用 `RS4Mini` 对象上选择 `appCommands.useProfile('ronin-2.2.2')` 后，新增以下设备设置接口。原生继承到 `RSGimbal`。新接口未进行实机验证，没有新增高级运动功能，也没有开放任意参数写入。

## 接口与来源

| Node/Web 方法 | 字段 / 返回 |
|---|---|
| `getCustomFollowSettings({timeoutMs?})` | `settings:{enabled,pitch,roll,yaw}`，均为布尔值 |
| `setCustomFollowSettings({enabled?,pitch?,roll?,yaw?,timeoutMs?})` | 至少一个设置字段，值必须是布尔值 |
| `getMotorSettings({timeoutMs?})` | `settings:{enabled,forbidSelfie,forbidVertical,roll360}` |
| `setMotorSettings({enabled?,forbidSelfie?,forbidVertical?,roll360?,timeoutMs?})` | 至少一个设置字段，值必须是布尔值 |

Python 同名方法，使用关键字参数；另有对应 snake_case 别名。原生方法为 `getCustomFollowSettingsWithTimeoutMs:completion:`、`getMotorSettingsWithTimeoutMs:completion:`、`setCustomFollowSettings:timeoutMs:completion:`、`setMotorSettings:timeoutMs:completion:`；设置为布尔字典，completion 规则与 [参数事务](APP_COMMANDS.md) 相同。

读取返回原有 AppParameterReply 字段，另有 `settings`、`rawValue` 和 `unknownBits`。写入返回关联 ACK，以及 `previousRawValue`、`requestedRawValue`、`requestedSettings`，不将请求值写进反馈缓存。所有结果仍标记 `deviceVerified:false`、`physicalCompletionVerified:false`；写后要另外回读，ACK 不能证明固件行为或配置持久化。

静态证据来自固定当前 App 的 `DJIGimbalRonin2Abstraction` 八个 setter、公共写入方法、BaseCommand 构造及按名字加载的参数记录。HG724 继承 HG702→Ronin2；这是继承源码证据，不是固件支持或 App UI 启用所有设置的证据。类型/范围只用于拒绝超出来源的写入，不能称为硬件安全区间。

| 命名参数 | 索引/宽度 | 位定义 |
|---|---|---|
| `ronin_custom_follow_setting` | 132 / 1 | bit0启用；bit1 Pitch；bit2 Roll；bit3 Yaw |
| `motor_special_cmd` | 35 / 1 | bit0电机禁用（与 enabled 反向）；bit4禁止自拍；bit5禁止竖拍；bit6启用360° Roll |

这些是源码字段含义；`roll360` 设置本身不是360°旋转轨迹。自定义跟随位不是 PF/PTF/FPV 预设，不推断其他模式联动、屏幕开关或所需工作模式。设置 `enabled` 可能改变电机状态，实际作用等待统一实机验收。

## 事务规则

设置先验证参数并复制快照，取得同一个设备操作槽，停止连续运动，再发 `04:10` 读取当前字节；按指定字段修改后，发 `04:0F`，等待严格关联的状态 ACK。整个读写期间不释放操作槽。应用仍只有高级入口；这是封装共享设备寄存器所需的 SDK 协议事务，不能计作新增固件命令或高级运动算法。

未指定的位保留，使用刚读到的值，不使用缓存或默认值。电机字节中未知位也保留。自定义跟随若读到大于15的值，读取仍保留原值和未知位，但设置抛 `RS4MINI_UNSUPPORTED_VALUE`，不抹掉未知位或发送超出源码校验范围的值。

两阶段共享一个单调时钟截止时间，默认3000ms，允许大于0且不超过60000ms。截止时间从停止前置步骤完成后开始；停止/写入清理另有原来的 I/O 截止时间。读取失败、截断、不匹配、设备拒绝或取消时，不继续写入；写入已发送后取消不承诺回滚。停止、断连及 Web 失焦可取消整个设置事务，重连不重放。读取可与 Node/Python 运动共存；原生读取依旧独占并停止，详见参数文档。

SDK 不提供设备端 compare-and-swap；事务所有权只覆盖本 SDK 实例。其他控制端若同时改相同字节，无法保证不会发生竞争。这里不把一次读写声称为固件原子事务。

离线例子：当前自定义值 `0e`，仅启用并关闭 Pitch，写入 `84 01 0d`，保留 Roll/Yaw；当前电机值 `cf`，启用电机、禁止自拍并关闭360°Roll，写入 `23 01 9e`，保留未指定和未知位。它们是合成向量，没有发送到设备。

## 可复现证据

[ronin-settings-evidence.json](../protocol/research/ronin-settings-evidence.json) 固定九个方法指纹、八个掩码与分支极性、继承链及两条按名字解析的记录。不输出完整厂商指令体。读取/写入打包和返回码证据沿用 [代码恢复说明](../tools/research/CODE_RESTORATION.md) 与 [APP_COMMANDS.md](APP_COMMANDS.md)。

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_settings_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --dex work/research/code-final/business-05-code-restored.dex \
  --output work/research/reproduced-settings-evidence.json
```

提取器先校验 APK 与恢复视图 SHA256，再按真实构造参数解析命名键，核对唯一参数名、位掩码、分支极性和 setter 派发。不按重复索引反查名称，不执行 App/JNI，不依赖硬件。默认离线测试只使用标准库边界测试；实际复现另用隔离 Androguard4.1.3。

PF/PTF预设、真实单轴回中、校准/电机数值调参、原生程序及系统管理命令仍未完成。48条清单不是完整枚举，两个完整性门槛保持false。
