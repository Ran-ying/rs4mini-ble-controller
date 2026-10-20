# 程序命令 25/37/62/63 八段调用与相机隔离重审

2026-10-20；运行时 0.7.33 / 0.3.33。工具 [ronin_program_prefix_trace.py](ronin_program_prefix_trace.py)，证据 [ronin-program-prefix-evidence.json](../../protocol/research/ronin-program-prefix-evidence.json)。历史 [PROGRAMS.md](PROGRAMS.md)、[PROGRAM_ENTRY.md](PROGRAM_ENTRY.md)、[TRACK_POINTS.md](TRACK_POINTS.md)。

## 结论（本阶段完成条件）

八段 PREFIX 扫描下，四类协议模型的类外调用**全部在 Create\* UI**（bank03），**无 HG724 具名抽象直接 invoke**。存在 start/stop 与 CreateUtils `stop*PreviewWork`，但：

- 全景 `doPack` 仍含 **`mExposure`**，UI start 调用 `setExposureTime` / `setPictures`
- 轨迹 API 含 **`setRecordOrPreview`**
- **未建立**与相机曝光/拍摄隔离的可靠停止

因此 **`pureGimbalProgramPrimitiveOpenable=false`，不开放程序执行 SDK**。ActualPose≠MotorAngle/04:05 的既有路点研究仍有效，不能把关节反馈当固件轨迹角。

| 命令 | 模型类 | 定义银行 | 类外调用数 |
|---|---|---|---:|
| 04:25 | DataGimbalSetDelayTimelapseParams | 05 | 12 |
| 04:37 | DataRonin2SetTimelapseParams | 05 | 3 |
| 04:62 | DataGimbalSetTrackStatus | 05 | 12 |
| 04:63 | DataGimbalSetPanoramaParams | 05 | 4 |

01/07 无上述外部调用。

## 复现

```sh
PYTHONPATH=work/research/analysis-venv/lib/python3.*/site-packages:tools/research \
  work/research/analysis-venv/bin/python tools/research/ronin_program_prefix_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/prefix-restored-final-b \
  --output work/research/program-prefix-reproduced.json
python3 -m unittest discover -s tools/research -p test_ronin_program_prefix_trace.py -v
```
