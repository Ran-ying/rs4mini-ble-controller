# 04:14 / 04:0C / 04:4C 八段运动路径重审

2026-10-20；运行时保持 0.7.33 / 0.3.33。工具 [ronin_motion_prefix_trace.py](ronin_motion_prefix_trace.py)，证据 [ronin-motion-prefix-evidence.json](../../protocol/research/ronin-motion-prefix-evidence.json)。历史见 [ANGLES.md](ANGLES.md)、[ANGLE_CONTEXT.md](ANGLE_CONTEXT.md)、[RESET_ROUTES.md](RESET_ROUTES.md)。

不执行厂商代码；不开放 14/0C 发送；不把 0C 替换现有主机 04:01 速度；不推广 SpecialControl 混合体；无按轴回中。

## 04:0C 当前 App 源布局

`DataGimbalSpeedControl.doPack`：7 字节，**yaw / roll / pitch** 各 uint16 LE（int 低 16 位），字节6：`permission<<7 | multiControl`。

基础 `rotate` 的 SPEED 分支：各轴先收窄为 **float32**，再 Java `float-to-int`（向零；NaN→0；±Inf 饱和到 int32），再 `mul-int/lit8` ×10（int32 环绕）。**不是** float32×10。例：`1.99999999` → 20，`1.9` → 10。并仍调用 `justSendPauseData`（EYE/SINGLE 依赖未对直连 BLE 解决）。

Ronin UI `RoninGimbalControler`：`send` 写 permission+yaw+pitch（**不写 roll**）后 `start()`；`stop` 仅 permission+`start()`，**扫描体内不先清零三轴**，先前字段可能残留。

类外调用：UI send/stop、基础 rotate、以及 M200 飞控（他型号）。**无 HG724 专用入口**；未开放原生速率 SDK。

## 04:14

类外直接调用仍仅基础 `DJIGimbalAbstraction.rotate`；HG724 无 rotate 覆盖。能力/接收链历史证据保留；本机 index/地址、参考系、ACK/完成/中止、EYE 依赖适用性仍缺，发送关闭。

## 04:4C

八段类外调用 8 个：LeftBar、三处既有 UI 回中、Focus 电机回中（相机排除）、基础 resetGimbal/setGimbalMode、DT501 UVC。非相机/焦点 6 个。无按轴回中字符串/证据；MODE 枚举仍不是按轴。保持既有 FE01 三轴回中。

01/07 对本三项无新增外部调用。

## 复现

```sh
PYTHONPATH=work/research/analysis-venv/lib/python3.*/site-packages:tools/research \
  work/research/analysis-venv/bin/python tools/research/ronin_motion_prefix_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/prefix-restored-final-b \
  --output work/research/motion-prefix-reproduced.json
python3 -m unittest discover -s tools/research -p test_ronin_motion_prefix_trace.py -v
```
