# 离线队列 D：程序型号与相机隔离

2026-10-20。工具 [ronin_queue_d_program_isolation_trace.py](ronin_queue_d_program_isolation_trace.py)，证据 [ronin-queue-d-program-isolation-evidence.json](../../protocol/research/ronin-queue-d-program-isolation-evidence.json)。接续 [PROGRAM_PREFIX.md](PROGRAM_PREFIX.md)。

## 子状态（由证据计算）

| 子项 | 当前状态 | 含义 |
|---|---|---|
| `bit_layout` | **`bit_layout_established`** | 04:25/37 `mInfoByte` 位图已从 setter 解出 |
| `call_values` | `statically_exhausted_needs_hardware` | Create 调用参数含运行时寄存器/字段；见 `dynamicBoundaries` |
| `camera_isolation` | `statically_exhausted_needs_hardware` | 线格式可打包预览/外设/曝光；固件是否允许无相机原语需本机测量——**不**声称静态已证伪或已成立 |
| `stop_semantics` | `statically_exhausted_needs_hardware` | CreateUtils/Create\* stop 链已追踪；设备停机效果与单例未清位需本机 |
| `model_entry` | `statically_exhausted_needs_hardware` | 无 HG724 具名程序方法 ≠ 无入口；产品/组件绑定需会话 |

整体 `status = compute_overall(substatuses)`：位图未建立 → `statically_unresolved`；任一面触及动态/会话边界 → `statically_exhausted_needs_hardware`；否则保持 `statically_unresolved`。`programExecutionOpened=false`；程序发送保持关闭。

## 位图（静态已证）

| 命令 | 要点 |
|---|---|
| 04:63 | doPack 含 **mExposure** |
| 04:62 | doPack 含 **mRecordOrPreview** |
| 04:25 | mInfoByte：bit0 mode、bit1 tripod、bit2 startStop、**bit3 ISPreview**、**bit7 controlExternalDevice**（OR 累加） |
| 04:37 | mInfoByte：bit0 mode、bit1 tripod、bit2 startStop、**bit3 startOrPreview** |

## Create 追踪要点

参数解析用 CFG + 到达定义（[ronin_dalvik_reaching.py](ronin_dalvik_reaching.py)）：分支汇合给出可证常量集合（如 `{0,1}`）或 `statically_unresolved`；不支持的写入使寄存器失效。未解析寄存器**不**算硬件边界，只会让 `call_values` 保持 `statically_unresolved`。

- 参数：常量（如 Follow `startTimeLapse` 上 `setISPreview(0)`）；方法参数（如 PathDelay `sendToDeviceStart(I)` 的 preview）；分支选择常量集（PathDelay `setControlExternalDevice` ∈ {0,1}，由 `mFocusMotorConnected`、`createFocusControlEnabled()`、航点数选择）。
- 实例：`getInstance()` / 字段 `mSetter` 复用；setter OR 累加进同一字节。
- Stop：`CreateUtils.stop*` 等设置 startOrStop 后 `start(callback)`；部分 stop 未显式清 preview 位。
- 型号：Create UI 走 midware 单例；PREFIX 无法单独钉死 RS 4 Mini 组件可达。

## 未证 / 需硬件

见证据 `dynamicBoundaries[].hardwareMeasurementsNeeded`。不开放 04:25/37/62/63 发送。
