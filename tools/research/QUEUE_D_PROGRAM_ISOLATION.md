# 离线队列 D：程序型号与相机隔离

2026-10-20。工具 [ronin_queue_d_program_isolation_trace.py](ronin_queue_d_program_isolation_trace.py)，证据 [ronin-queue-d-program-isolation-evidence.json](../../protocol/research/ronin-queue-d-program-isolation-evidence.json)。接续 [PROGRAM_PREFIX.md](PROGRAM_PREFIX.md)。

状态由 `compute_status(...)` **计算**：在 mInfoByte 位图与具名相机字段均证毕且交织成立、且尚无可靠隔离停止/型号入口时为 **`statically_exhausted_needs_hardware`**；位图未解完则为 `statically_unresolved`。`pureGimbalProgramPrimitiveOpenable=false`。

## 静态已证

| 命令 | doPack 字段要点 | 相机/录制交织 |
|---|---|---|
| 04:63 全景 | 含 **mExposure** | 是 |
| 04:62 轨迹 | 含 **mRecordOrPreview** | 是 |
| 04:25 | **mInfoByte**：bit0 mode、bit1 tripod、bit2 startStop、**bit3 ISPreview**、**bit7 controlExternalDevice** | 预览/外设位与云台控制同字节 |
| 04:37 | **mInfoByte**：bit0 mode、bit1 tripod、bit2 startStop、**bit3 startOrPreview** | 预览位与云台控制同字节 |

- 类外调用仍在 Create\* UI；Create 路径调用上述 preview/external setter。
- HG724 **无** track/panorama/timelapse 具名方法。
- 缺少 HG724 具名调用者 **≠** 无继承业务入口。

## 未证

- RS 4 Mini 型号/组件是否可达这些程序。
- 可靠停止且与曝光/拍摄隔离。

程序执行保持关闭。不把硬编码 `statically_exhausted_needs_hardware` 当证据：状态随位图/交织标志计算。
