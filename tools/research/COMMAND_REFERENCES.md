# 六段非相机命令引用矩阵与04:0D边界

2026-10-17，运行时仍0.7.19/原生0.3.19。工具ronin_command_refs.py固定APK与六段恢复视图哈希；不执行厂商代码、不导入SDK、不构造DUML或操作硬件。证据protocol/research/ronin-command-references.json。

扫描40个非相机枚举名，对应39个不同命令值（SetAngle/AngleControl同为0A），排除FocusControl/NotiFyCameraId及Other哨兵。共50个含引用方法，31个枚举名有枚举外字段引用，均只作为实现/分发候选；没有识别到字面量写包候选。遍历六段共254468个带code方法、3463422条指令，不是原始方法全部恢复或跨段去重计数。

“枚举外引用”只是CmdIdGimbal.CmdIdType类之外的静态字段读取/写入，可能只是命令类自己的start或入站处理/状态判断，不等于业务调用、HG724路径或实际发送。例SaveUserParams只有自身协议类start引用，与此前没有外部业务调用者的结论不冲突。

| 枚举名 | 命令值 | 枚举外引用方法数 |
|---|---|---:|
| Control | 04:01 | 2 |
| GetPushParams | 04:05 | 0 |
| RollFinetune | 04:07 | 1 |
| AutoCalibration | 04:08 | 1 |
| SetAngle | 04:0A | 2 |
| SetOnOrOff | 04:0D | 0 |
| SpeedControl | 04:0C | 2 |
| AngleControl | 04:0A | 2 |
| SetUserParams | 04:0F | 1 |
| GetUserParams | 04:10 | 2 |
| SaveUserParams | 04:11 | 1 |
| SubscribeGimbalParams | 04:12 | 2 |
| ResetUserParams | 04:13 | 1 |
| AbsAngleControl | 04:14 | 2 |
| GetPushType | 04:1C | 0 |
| GetPushUserParams | 04:24 | 0 |
| SetDelayTimelapseParams | 04:25 | 1 |
| GetPushAbnormalStatus | 04:27 | 0 |
| GetPushTutorialStatus | 04:2B | 0 |
| SetTutorialStep | 04:2C | 1 |
| GetPushSensorCalibrationStatus | 04:30 | 0 |
| RoninSetParams | 04:31 | 1 |
| RoninGetParams | 04:32 | 2 |
| RobinPushBattery | 04:33 | 0 |
| SetHandleParams | 04:35 | 1 |
| GetHandleParams | 04:36 | 1 |
| SetTimelapseParams | 04:37 | 3 |
| GetPushTimelapseStatus | 04:38 | 1 |
| BalanceAdjust | 04:40 | 1 |
| SetCalibration | 04:6A | 1 |
| SetTrack | 04:62 | 9 |
| SetPanorama | 04:63 | 3 |
| GetPushPanorama | 04:64 | 1 |
| GetPushTrackAndTimelapse | 04:6B | 1 |
| GetPushCalibration | 04:6E | 1 |
| SetPushPeripheralStatus | 04:66 | 2 |
| GetPushExternalDeviceData | 04:69 | 1 |
| GetPushHandheldStickState | 04:57 | 0 |
| SetHandheldStickControlEnabled | 04:58 | 1 |
| ResetAndSetMode | 04:4C | 2 |

## SetOnOrOff的实际边界

命令构造参数为名称SetOnOrOff、ordinal5、data13，签名(String,int,int)；线上枚举值为04:0D，不能取ordinal5。短构造器不写cls/dataBase字段，没有显式Class参数；这不是出站实现工厂或“不支持”的证明。Control同样短构造器但有明确start引用及既有硬件证据，不能以缺Class参数判断缺实现。

六段未见SetOnOrOff枚举外字段引用，也未识别到cmdSet4/cmdId13字面量SendPack候选；假设的DataGimbalSetOnOrOff类名在这六段中无定义。名称仅是检索假设，不能据枚举机械生成类名或断言实现不存在。不据SetOnOrOff一词推断整机电源、休眠或电机控制，更不替代现有源HG724继承setMotorEnabled→MOTOR_SPECIAL_CMD/参数35反向bit0路径。

清单此前“通用命令方法已恢复”的套用描述对本条没有方法证据，现改为明确未知；其他仅枚举级条目也改成逐项核对方法存在性，不再把枚举恢复写成所有请求体已恢复。

## 负面检索与候选分析限制

GetPushParams没有枚举外引用，但04:05本机反馈已有历史硬件证据。由此可见零引用不是固件不支持证明。1/7段未恢复、剩余保护桩/无code方法、反射/动态/native/固件路径均未排除。

字面量分析只追踪线性语法中的SendPack对象、常量/简单别名以及CmdSet.GIMBAL.value，分支后丢弃状态，未知/宽寄存器写入失效。它不做完整CFG目标/异常表/别名/调用副作用分析，候选也不证明调用start或最终字段未被覆盖；literalResolutionComplete/literalCandidatesProveSend均false。未识别候选不排除绕过枚举的动态路径。

CmdSet.GIMBAL构造器带CmdIdGimbal对象实例，不能直接复用只处理字面量/Class参数的枚举解析器；工具单独校验前三个常量和该对象类型。首次解析按过窄假设拒绝后修正，没有放宽既有通用构造器解析。

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_command_refs.py --apk work/research/dji-ronin-2.2.2.apk --bank-dir work/research/code-banks --output work/research/command-refs-reproduced.json
```

11项新测试覆盖枚举字段与字符串分离、同对象/别名、GIMBAL构造和取value、未知/宽寄存器覆盖、分支、错误命令集/ID以及哈希先验。没有新增SDK发送或高级功能，不提供0D试探接口，全部命令和本机验收仍未完成。
