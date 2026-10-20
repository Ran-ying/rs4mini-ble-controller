# 04:14 rotate → pause/EYE → transport 端到端静态追踪

2026-10-20。工具 [ronin_rotate_eye_transport_trace.py](ronin_rotate_eye_transport_trace.py)，证据 [ronin-rotate-eye-transport-evidence.json](../../protocol/research/ronin-rotate-eye-transport-evidence.json)。固定 Ronin 2.2.2 APK 与 PREFIX_BANKS；分析主落在 bank05。不执行厂商代码；不开放 04:14 或 EYE AppState 发送。

接续 [ANGLES.md](ANGLES.md)、[ANGLE_CONTEXT.md](ANGLE_CONTEXT.md)、[STABILIZATION_DEPENDENCY.md](STABILIZATION_DEPENDENCY.md)、[MOTION_PREFIX.md](MOTION_PREFIX.md)。本页把**一条继承入口**从业务方法追到包层字段，并明确区分静态已证实与仍需硬件确认。

## 静态已证实（bytecode）

1. **入口。** `DJIGimbalAbstraction.rotate` 是 HG724 继承链上的实现；PREFIX 扫描未见 HG724 `rotate` 覆盖。缺少 HG724 具名 override **不等于**没有继承业务入口。
2. **暂停门。** SPEED（04:0C）与 ABS（04:14）分支在打包前都调用 `justSendPauseData()`：新建 `DataSingleSendAppStateForStabilization`，设 `GimbalState.START`，再调**无回调** `start()`。不等待业务 ACK 再发角度包。
3. **EYE 传输。** 无回调 `start()` 组装 `SendPack`：sender APP(2) → receiver **SINGLE(17) id 7**；CmdSet **EYE**；CmdId **AppState wire 98**；NEEDACK YES；EncryptType NO；再 `DataBase.start(SendPack)`。这不是云台命令集，也不是 04:62/04:60。
4. **暂停体。** `doPack` 两字节：gimbalState、cameraState 各一字节。rotate 路径下 START + 默认 camera NORMAL → 源体 `0100`。`START` 名字不证明物理已暂停。
5. **04:14 返回。** ABS 路径：`setReceiverId(getReceiverIdByIndex())` → `AbsAngleControl.start()` → 立刻 `CallbackUtils.onSuccess`。主机成功回调 ≠ ACK 接受 ≠ 物理到位；本方法内无完成/中止通知。
6. **索引映射。** `getGimbalIdInProtocol`：源 index 精确为 1 → id 2，其余 int → 0。`preprocessPack` 在已存 receiverID ≠ −1 时可覆盖 pack 的 receiverId。

## 仍需硬件 / 现场会话确认

- 直连 BLE / RS 4 Mini 是否必须发送 EYE/SINGLE/id7 AppState。
- 本机 gimbal index 与线上 receiver 地址。
- EncryptType.NO 是否等于最终 BLE 明文。
- 04:14 的 ACK/ccode、完成、取消/中止与物理运动。
- AppState START 之后是否有恢复/解除协议。
- init 之后能力表是否被动态改写；绝对角参考系与主机关节/姿态反馈的关系。

## 复现

```sh
PYTHONPATH=work/research/analysis-venv/lib/python3.*/site-packages:tools/research \
  work/research/analysis-venv/bin/python tools/research/ronin_rotate_eye_transport_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/prefix-restored-final-b \
  --output work/research/rotate-eye-reproduced.json
python3 -m unittest discover -s tools/research -p test_ronin_rotate_eye_transport_trace.py -v
```

独立提取两次应逐字节一致。运行时保持 0.7.33 / 0.3.33；inventoryComplete 与 advancedDevelopment 仍 false。
