# 离线队列 A：EYE 必要性 / 索引地址 / 加密终态 / 动态能力

2026-10-20。工具 [ronin_queue_a_semantics_trace.py](ronin_queue_a_semantics_trace.py)，证据 [ronin-queue-a-semantics-evidence.json](../../protocol/research/ronin-queue-a-semantics-evidence.json)。接续 [ROTATE_EYE_TRANSPORT.md](ROTATE_EYE_TRANSPORT.md)、[ANGLE_CONTEXT.md](ANGLE_CONTEXT.md)、[CALIBRATION_TRANSPORT.md](CALIBRATION_TRANSPORT.md)。

四项状态由 `compute_substatus(...)` **计算**（静态事实齐且本机未证 → `statically_exhausted_needs_hardware`；非硬编码常量）。静态能证的已证完；完成条件中的本机/直连验证未满足，故不标完成。

## EYE/SINGLE 对直连 BLE 是否必须

| 静态已证 | 未证（需硬件/无 DJI 栈的直连会话） |
|---|---|
| App `rotate` 的 SPEED/ABS 分支各无条件调用 `justSendPauseData` | 直连 BLE 省略该包是否仍被固件接受 |
| 全 PREFIX 仅 ROOT 定义；调用点仅 `rotate`；HG724 无覆盖 | RS 4 Mini 是否要求 SINGLE/id7 组件 |
| 其它 `DataSingleSendAppStateForStabilization` 引用为相机变焦路径 | 物理暂停效果 |

## 本机 index / 地址

| 静态已证 | 未证 |
|---|---|
| 构造默认 `index=0`；`init(..., index, ...)` 写入字段 | 现场 HG724 实例的 index 实参 |
| `getReceiverIdByIndex` → `getGimbalIdInProtocol`：仅 index==1 → 2，其余 → 0 | 线上 receiver 字节 |

## 最终加密路径

| 静态已证 | 未证 |
|---|---|
| CmdSet EYE=10、GIMBAL=4；`isNeedEncrypt` 对 EYE/98 与 GIMBAL/20 为 true | 会话 `isOldFirmware` 实值 |
| 业务 `EncryptType.NO` 可在 `isOldFirmware==false` 时被 SIMPLE 重写 | `native_rcDataDeal` 实际输出（离线不执行 JNI） |

## 动态能力

| 静态已证 | 未证 |
|---|---|
| 静态 init 合并见 ANGLE_CONTEXT；`rotate` 绝对角分支调用时读 min/max | 本机 ParamInfo 是否改写 ADJUST_* 范围 |
| Ronin2 存在 `BaseCommand`→ParamInfo range→`addMinMaxToCapability`；HG724 继承 Ronin2 | 动态变更的时机与值 |

不开放 EYE AppState / 04:14 发送。

```sh
PYTHONPATH=work/research/analysis-venv/lib/python3.*/site-packages:tools/research \
  work/research/analysis-venv/bin/python tools/research/ronin_queue_a_semantics_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/prefix-restored-final-b \
  --output work/research/queue-a-reproduced.json
python3 -m unittest discover -s tools/research -p test_ronin_queue_a_semantics_trace.py -v
```
