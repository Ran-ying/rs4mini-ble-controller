# 按轴跟随与摇杆档位（0.7.9 / 原生0.3.9）

应用仍通过RS4Mini/RSGimbal统一入口和同一设备连接使用appCommands。显式选择ronin-2.2.2来源配置后，新增get/setFollowSettings与get/setRcSettings。它们是设备参数事务，不是PF/PTF/FPV模式预设或高级运动任务，没有实机验收。

## 六组命名参数

| 接口组 | parameter | 命名参数 | index |
|---|---|---|---:|
| Follow | speed | ronin_follow_speed_mode | 65 |
| Follow | acceleration | ronin_follow_acce_mode | 71 |
| Follow | deadZone | ronin_follow_dead_zone_mode | 66 |
| Rc | speed | ronin_rc_speed_mode | 67 |
| Rc | deadZone | ronin_rc_dead_zone_mode | 68 |
| Rc | smoothing | ronin_rc_smooth_mode | 69 |

记录均typeINT08U/size1、普通04:10读取/04:0F写入。一个字节包含Pitch bits2..3、Roll bits4..5、Yaw bits6..7；每轴0 custom、1 low、2 middle、3 high。低两位未解释，返回unknownBits且写入保留。不把这些档位换算成角度、速度或百分比。

custom只选择设备已有的自定义数值，不设置该数值，也不等于启用自定义跟随轴。各轴custom数值参数与PF/PTF/FPV完整模式仍需另行封装/验证。

## Node与Web

```js
// 以下调用会访问硬件，仅供明确授权的实机会话；默认测试不执行。
gimbal.appCommands.useProfile('ronin-2.2.2');
const before = await gimbal.appCommands.getFollowSettings({parameter:'speed'});
const ack = await gimbal.appCommands.setFollowSettings({parameter:'speed',yaw:'low'});
const rc = await gimbal.appCommands.getRcSettings({parameter:'smoothing'});
await gimbal.appCommands.setRcSettings({parameter:'smoothing',pitch:'custom',roll:'middle'});
```

读取返回AppSettingsReading：settings含pitch/roll/yaw三轴档位，另有rawValue、unknownBits和原始参数记录。例9b解码为Pitch middle、Roll low、Yaw middle，unknownBits=3。第二头字节仍保留raw，不推断为宽度。

写入要求parameter和至少一个轴；只接受custom/low/middle/high，拒绝布尔、数字、medium、pan/tilt、任意index或整字节覆盖。验证并复制输入后，先停止主机连续运动，取得操作槽，发送04:10读取当前值，修改指定两位字段，再发送04:0F并等待关联ACK。示例原ff、Yaw改custom，写体为41 01 3f；其余轴和低两位不变。

读取、修改、ACK共用一次操作所有权与响应总截止时间。timeoutMs默认3000，范围>0..60000，响应总时间从停止前置步骤之后开始；I/O/清理沿用已有有界机制。取消、读取失败或畸形响应不继续写入，超时不自动重发。成功返回previousRawValue、requestedRawValue、requestedSettings及AppCommandReply；ACK不代表实际生效/持久化，physicalCompletionVerified仍false。

这是两个BLE命令组成的寄存器事务，不是固件原子操作；同一实例内互斥不能保证别的设备控制端不同时改值，也不承诺回滚。已发送的写入无法由主机取消撤销。

## Python与原生

Python提供同名camelCase方法和get_follow_settings/set_follow_settings/get_rc_settings/set_rc_settings，parameter等选项均为关键字参数。通过已有app_commands/appCommands对象访问。

原生RSGimbal继承：

- getFollowSettings:timeoutMs:completion:、getRcSettings:timeoutMs:completion:，首参是parameter字符串。
- setFollowSettings:settings:timeoutMs:completion:、setRcSettings:settings:timeoutMs:completion:，settings只含至少一个轴的档位字符串。

原生会复制可变字符串值。Node/Python纯读取可与主机运动共存，原生读取也独占并先停止；所有端的写入从读取到ACK均独占。不增加调参面板按钮或启动UI。

## 来源与待验收

SDK段business05提供六个命名setter→setRonin2CommonUserParam→普通0F/10的链及唯一资源记录。新恢复UI段business03的ConfigSelectSeekbarDialog.updateView明确按2/4/6位提取Pitch/Roll/Yaw，onItemChange打包其他轴；DJIGimbalRCControlType提供custom/low/middle/high枚举。静态复现工具核对固定APK和两个恢复视图哈希，共18方法指纹。证据见 [ronin-follow-modes-evidence.json](../protocol/research/ronin-follow-modes-evidence.json)。

App部分UI设置会重组整字节，本SDK使用新鲜读取保留未指定字段和未解释低两位。没有据类名或UI存在推断HG724固件实际启用；型号UI分支、低两位含义、实际接受/生效/持久化仍待本机验收。此前40个引用方法的证据只描述调用方扫描范围，不等于所有相关业务均已审计。

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_follow_modes_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --sdk work/research/code-banks/business-05-code-restored.dex \
  --ui work/research/code-banks/business-03-code-restored.dex \
  --output work/research/reproduced-follow-modes.json
```

本批仅离线研究、测试与构建，没有扫描、连接、移动设备、启动UI或执行厂商代码；全部命令和新增高级开发门槛仍false。


## 0.7.10 普通数值SDK

18项普通跟随/RC数值已同步四端，1/2字节小端与无符号异常原值按上下文解码，单项写入独占到ACK、取消无重放。不自动切档位/预设/输入源，activePresetVerified:false，独立配置和实机效果仍待完成。Node120/Web14/Python各97/native83+113+3/research53，类型/边界/构建通过，三端目录逐项匹配源码。无硬件/UI或高级新增。详见 [APP_NUMERIC_TUNING.md](APP_NUMERIC_TUNING.md)。
