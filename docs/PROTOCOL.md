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
