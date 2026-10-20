# 离线队列 C：完成 / 中止静态契约

2026-10-20。工具 [ronin_queue_c_completion_abort_trace.py](ronin_queue_c_completion_abort_trace.py)，证据 [ronin-queue-c-completion-abort-evidence.json](../../protocol/research/ronin-queue-c-completion-abort-evidence.json)。

状态：**`statically_exhausted_needs_hardware`**。

## 静态已证

- `rotate` 仅调用 `AbsAngleControl.start()V`（无回调），随后 `CallbackUtils.onSuccess`；PREFIX 上 ABS `start` 的唯一调用者是 `rotate`，且不用 callback 重载。
- ABS 包层 `NEEDACK.YES`；无回调 `start` → `DataBase.start(SendPack)`；callback 重载 → `DataBase.start(SendPack, callback)`（可关联 ACK，但 rotate 未用）。
- 轨迹 `setStartOrStop` 写程序阶段字段；停止相位是程序命令，不是 04:14 运动 abort。
- 稳定等待（既有 STABILIZATION 专题）不是角度到位通知。

## 未证

- ACK 接受、ccode、物理到位、取消/断线恢复。

不开放发送；不把主机 onSuccess 当完成。
