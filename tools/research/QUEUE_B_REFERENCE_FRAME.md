# 离线队列 B：参考系静态绑定

2026-10-20。工具 [ronin_queue_b_reference_frame_trace.py](ronin_queue_b_reference_frame_trace.py)，证据 [ronin-queue-b-reference-frame-evidence.json](../../protocol/research/ronin-queue-b-reference-frame-evidence.json)。接续 [TRACK_POINTS.md](TRACK_POINTS.md)。

状态由 `compute_status(...)` **计算**（当前为 **`statically_exhausted_needs_hardware`**，非硬编码常量）。

## 静态已证

- 04:66 `DataType`：ActualPose 标签 34/35/36 与 MotorAngle 16/17/18 **不相交**（PREFIX bank05 现场提取）。
- 八段扫描中，**没有**方法同时直接引用 ActualPose getter 与 `DataGimbalGetPushParams`（04:05 推送类）——未发现源码层“同一参考系”等式。
- `DataGimbalAbsAngleControl.doPack`：yaw/roll/pitch short + `controlMode`/invalid 位；**无**名为参考系/坐标的字段。`controlMode` 是绝对/相对控制位，不是地球系/机体系证明。
- 基础 `rotate` 走 AbsAngleControl，**不**读 peripheral ActualPose。

## 未证（需硬件）

- ActualPose / MotorAngle / 04:05 姿态 / 04:05 关节 的物理零点、轴指向与是否同值。
- 轨迹路点角能否用主机 `getJointAngles()` 代替。

不开放 04:14/04:62 发送；不改现有反馈映射。
