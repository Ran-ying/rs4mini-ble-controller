# 离线队列 D：程序型号与相机隔离

2026-10-20。工具 [ronin_queue_d_program_isolation_trace.py](ronin_queue_d_program_isolation_trace.py)，证据 [ronin-queue-d-program-isolation-evidence.json](../../protocol/research/ronin-queue-d-program-isolation-evidence.json)。接续 [PROGRAM_PREFIX.md](PROGRAM_PREFIX.md)。

状态：**`statically_exhausted_needs_hardware`**。`pureGimbalProgramPrimitiveOpenable=false`。

## 静态已证

| 命令 | doPack 字段要点 | 相机/录制交织 |
|---|---|---|
| 04:63 全景 | 含 **mExposure** | 是 |
| 04:62 轨迹 | 含 **mRecordOrPreview** | 是 |
| 04:25 / 04:37 | 含 **mInfoByte** 等 | 信息字节内相机语义**未在本审计解完**，不作“无相机” |

- 类外调用仍在 Create\* UI；HG724 **无** track/panorama/timelapse 具名方法。
- 缺少 HG724 具名调用者 **≠** 无继承业务入口。

## 未证

- RS 4 Mini 型号/组件是否可达这些程序。
- 可靠停止且与曝光/拍摄隔离。

程序执行保持关闭。
