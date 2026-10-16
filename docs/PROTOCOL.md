# RS 4 Mini BLE 协议记录

这是本项目的实现记录，不是 DJI 官方协议。偏移均从 payload 的第一个字节开始计算。

## BLE 和 DUML

| 项目 | 值 |
|---|---|
| Service | `FFF0` |
| Notify | `FFF4` |
| Write without response | `FFF5` |
| APP / GIMBAL 地址 | `02 / 04` |
| 发送切片大小 | 20 字节 |
| 默认速度发送频率 | 15 Hz |
| 已观察到的 `04:05` 反馈频率 | 约 1 Hz |

DUML 编码结构：

| 帧偏移 | 内容 |
|---:|---|
| 0 | 起始字节 `55` |
| 1–2 | 10-bit 总长度；byte 2 同时包含 `04` 版本位 |
| 3 | 前三字节的 CRC8 |
| 4–5 | sender / receiver |
| 6–7 | sequence，uint16 LE |
| 8 | flags |
| 9–10 | command set / command id |
| 11… | payload |
| 最后两字节 | 帧末尾之前所有字节的 CRC16，uint16 LE |

CRC8 初值 `77`，反射多项式 `8C`；CRC16 初值 `3692`，反射多项式 `8408`。
`node/src/protocol.js` 是编码参考，`node/src/telemetry.js` 负责接收重组及校验。
BLE 通知可能分片或粘包，不能把每个通知直接当作完整 DUML 帧。

## 速度和回中

速度 `04:01` payload 长 9 字节：

```text
int16 LE tilt
int16 LE roll
int16 LE pan
int16 LE zero = 0
uint8 source = 02
```

每轴 RC 值是 `1024 + round(clamp(input,-1,1) * 660)`。连续发送保持速度，
停止时发送三个全零输入对应的中位帧。sequence=`0100` 的停止黄金向量：

```text
551604fc020400010004010004000400040000027705
```

三轴回中 `04:4C`：payload=`FE 01`，flags=`40`。没有验证可单独指定轴的回中命令。

## `04:05` 姿态与关节角

原始测试中为 49 字节 payload，字段如下：

| 数据 | 偏移 | 编码 |
|---|---:|---|
| Attitude Pitch | 0 | int16 LE / 10，度 |
| Attitude Roll | 2 | int16 LE / 10，度 |
| Attitude Yaw | 4 | int16 LE / 10，度 |
| modeFlags | 6 | uint8；位语义未完整验证 |
| rollAdjust | 7 | int8；不用于位置闭环 |
| yawAngle 辅助字段 | 8 | int16 LE / 10；不用于位置闭环 |
| limitFlags / stateFlags | 10 / 11 | uint8；位语义未完整验证 |
| Joint Yaw | 16 | int16 LE / 100，度 |
| Joint Pitch | 20 | int16 LE / 10，度 |
| Joint Roll | 22 | int16 LE / 10，度 |
| 疑似四元数 | 24 / 28 / 32 / 36 | 四个 float32 LE，分量顺序未验证 |

姿态角会在 ±180° 环绕，不能直接用未处理环绕的数值差计算运动量。
关节角和平台姿态是不同坐标量。反馈中的零点不代表当前安装姿态的视觉水平或构图中心。
已实测的 Joint 角误差到速度指令方向：Pan `+`、Tilt `-`、Roll `+`。

## 查询和未采用命令

- `04:02` 空 payload 位置查询：在测试设备上未观察到有效响应。
- `04:1E` 空 payload degree-info 请求：有 `00` 成功响应，但未观察到反馈频率提高。
- 外部协议研究涉及 `04:0A` 和 `04:14` 绝对角命令；RS 4 Mini 的坐标语义和
  兼容性尚未实机验证。本 SDK 的 `moveTo()` 不使用它们。
- 官方 DJI R SDK 中的 `AA` CAN 帧协议与这里的 `55` BLE DUML 不相同，不能直接混用。

## 研究入口

这些是开发过程中查阅过的外部资料入口，不代表它们为本项目 RS 4 Mini 映射背书：

- [DJI RS SDK](https://www.dji.com/rs-sdk)
- [lib-osmo-ble](https://github.com/yigitkonur/lib-osmo-ble)
- [dji-firmware-tools gimbal dissector](https://github.com/o-gs/dji-firmware-tools/blob/master/comm_dissector/wireshark/dji-dumlv1-gimbal.lua)

以后变更协议字段时，优先提供本设备的分轴运动或离线合成帧证据，并在这里记录验证范围。

## 非相机扩展的研究配置（尚未验证 RS 4 Mini）

本轮只研究和运行离线测试，没有对稳定器发出新增命令。

| 配置/来源 | 本项目采用的内容 | 验证边界 |
|---|---|---|
| [RS 3 原始研究](https://github.com/jdesbonnet/dji_rs3_control/blob/689884f2249e721c5b65c9c74804caddc1e7a68c/rs3_ble_protocol_spec.md) | `04:14` Pan/Roll/Tilt 十分之一度、无效轴掩码；`04:0C` 同次序原生速率；`04:0F` 休眠/唤醒 | 原作者只实测部分 Pan 行为；其他轴、控制位、末参数单位与本型号均需验证 |
| [RS 3 Mini 原始实现](https://github.com/b-rutledge-code/rs3mini-bridge/blob/b64315754bb47be76d862ae8860764267215a7cf/lib/session-setup.js) | `04:0F` 型号独立的休眠字节 | 与 RS 3 字节不同，因此必须显式选择配置 |
| [RS 3 Mini 状态实现](https://github.com/b-rutledge-code/rs3mini-bridge/blob/b64315754bb47be76d862ae8860764267215a7cf/lib/telemetry.js) | `0D:02` 的原始字段和候选百分比，`04:66` TLV | 本项目严格检查端点/长度；保留原始量，不用该布局覆盖 RS 4 Mini 关节角 |

`experimental.absolute()` 按省略轴设置无效位；`parameterByte` 必须由调用方显式提供，
不把未确认的末参数解释成秒。`observeMs` 只是本地观察时长，不是固件运动时间或到位判断。
`experimental.rateFor()` 的清理先尝试 `04:0C` 零速/释放，再发送普通中位帧。
这些写入均不能证明固件会执行或能够中断自身的动作。

`experimental.query()` 只开放 version=`00:01`、position=`04:02`、
controlStatus=`04:0B`、type=`04:1C`，匹配同连接、sequence、`04→02`、命令及响应位。
它不开放任意命令、固件更新或校准触发；超时表示没有观察到关联响应，不能直接判定固件不支持。

研究还发现校准 `04:08` 在 RS 3 上可能自主运动，且额外流量会干扰校准；
本轮只解析候选进度 `04:30`，尚未开放触发接口。真正单轴回中、跟随模式参数、
完整校准与电机调参、原生轨迹/全景程序仍需补充协议依据和受控验证。
Osmo 示例的角度次序与这些 RS 资料冲突，不能直接移植。

四元数接口只提供显式分量顺序下的标准右手内禀 ZYX 数学转换，
结果带 `deviceConventionVerified:false`；没有自动识别 RS 4 Mini 坐标约定。

## 0.7.1 设备模块审计

现有编解码/发送已从主机运动算法中独立；详见 `ARCHITECTURE.md`。
`requestDegreeInfo()` 补齐 04:1E 空负载请求和关联原始响应封装；没有对硬件执行，不解释新的响应字段或宣称增频。
所有已知命令和未知缺口在 `../protocol/COMMANDS.json` 与 `SDK_COMMANDS.md` 中逐项记录。
这份清单不构成完整固件 BLE 指令表，未完成本机语义和枚举证明前不进入新增高级功能阶段。

## 0.7.2 被动用户参数候选解析

依据 [o-gs 原始 DUML 解码器](https://github.com/o-gs/dji-firmware-tools/blob/master/comm_dissector/wireshark/dji-dumlv1-gimbal.lua)
（本轮检查的文件 Git blob：`544f758ee1890c0be55687f8db52c970241d3736`），以及已登记 RS 3 来源的
`04:10 payload=12` / 响应 `00120100` 样本，显式研究配置支持以下候选格式：

- 仅 `04→02`、command-set=04、响应位 80 的消息进入新解析分支。
- 04:10：首字节为原始返回码；后续正索引项为 index / size / raw bytes，宽度严格限定 1/2/4/8。
  旧格式中的负 int8 项作为逐项 errorCode 保留。数组保留重复索引；截断、零宽度或未知宽度拒绝。
- 04:0F：仅一字节响应返回原始 statusCode。既有研究 sleep 布局不受影响。
- 新结果为 `user-parameters` / `user-parameter-ack`，附 `layoutSource:'legacy-duml'` 与
  `deviceVerified:false`。不会根据资源表自动命名参数、解释有符号/浮点数或判定本机兼容。

该来源是早期其他产品格式，不是 RS 4 Mini 字段验证。显式研究配置默认不启用；本轮不增加查询或写入接口。
官方 Ronin APK 的可读枚举和参数资源作为独立事实保存，不能替代协议布局与本机证据。


## 后续 MSDK 交叉证据

官方 provided 4.18 JAR 的不可达字节码尾部提供旧版 04:4C、04:32、04:35/36 候选结构，
只供离线核对，详见 [研究说明](../tools/research/MSDK_V4.md)。它没有恢复当前 Ronin App 的有效打包方法。
旧回中枚举与本机 FE01 三轴回中存在语义差异；接收包可能先剥离返回码，业务方法偏移不能直接复制到 BLE 解码器。
不据此改变现有研究配置或本机反馈映射，没有新增发送接口。


## HG724 型号与参数资源关联（2026-10-16）

可读 App 指令已把展示名 DJI RS 4 Mini 与 BLE 前缀 dji rs4 mini- 关联到 HG724。
HG724 类型枚举值 103 仅为 App 事实，不是已解码线上字段或本机查询结果。
专属类注册 FollowModeSensitivity，但设置方法与参数加载仍为保护桩，未恢复具体命令/索引/载荷。
两份资源原名分别为 gimbal_param_infos（res/DB.json）和 ronin2_gimbal_param_infos（res/jy.json），
不能据资源名或继承关系认定本机采用哪一份。完整证据与复现见 [HG724.md](../tools/research/HG724.md)。
本轮只增加离线研究工具，SDK/原生版本、48 条清单及完整性门槛不变，没有硬件操作。


## 当前 App 原代码备份恢复（2026-10-16）

在 classes6/business-05 的 fdex/dgc2 尾部发现原始代码备份，19,436 条记录逐一匹配方法 code_off 槽位、完整长度和指令单元数，恢复为不执行的离线视图。
HG724 跟随灵敏度 setter、参数管理器读取 gimbal_param_infos 的路径及参数写入打包已可读：命名参数 cmd_follow_mode_sensitivity 为 index150/size1，04:0F 源码载荷为 960100 或 960101。
当前复位命令确认是 mode+布尔 reset，而非旧 SDK 按轴枚举。本轮只添加恢复与离线核对工具，未新增 SDK/UI 发送或解码接口，也没有操作硬件；整个协议和本机验收仍未完成。
复现、指纹、适用范围与剩余缺口见 [CODE_RESTORATION.md](../tools/research/CODE_RESTORATION.md)。此前“setter/加载仅见保护桩”的记录属于旧 metadata-only 阶段。


## 0.7.3 当前 App 参数事务

显式来源 SDK 的04:0F/04:10返回码与高索引解码、外部宽度上下文及来源边界见 [APP_COMMANDS.md](APP_COMMANDS.md)。Ccode.OK=0；返回码与业务索引分离，第二头字节不解释为宽度。不是新硬件证据。
