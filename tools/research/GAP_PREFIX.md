# 04:0D / 04:2C / 04:0A 八段 PREFIX 缺口重审

2026-10-20；运行时保持 0.7.33 / 0.3.33。工具 [ronin_gap_prefix_trace.py](ronin_gap_prefix_trace.py)，证据 [ronin-gap-prefix-evidence.json](../../protocol/research/ronin-gap-prefix-evidence.json)。历史六段分别见 [COMMAND_REFERENCES.md](COMMAND_REFERENCES.md)、[TUTORIAL.md](TUTORIAL.md)、[ANGLES.md](ANGLES.md)，不得改写冒充本轮。

不执行厂商代码，不开放三项发送。

## 方法

固定 APK 与八段 `PREFIX_BANKS` 哈希全部通过后解析。逐段记录：假设/真实类是否定义、类外 `invoke`、枚举类外的 `sget/sput` 字段引用。01/07 单独汇总。

## 结果摘要

| 命令 | 类定义银行 | 类外直接调用 | 枚举外引用 | 发送 |
|---|---|---|---|---|
| 04:0D SetOnOrOff | 假设 `DataGimbalSetOnOrOff`：**无** | 0 | 0 | 未开放 |
| 04:2C SetTutorialStep | bank05 | 0 | 1（自身 `start`） | 未开放 |
| 04:0A SetAngle / AngleControl | bank05 | 2（均 DT501 UVC→SetAngle） | 4（两类自身 `start`） | 未开放 |

- 0D：枚举 wire **13**、三参无 Class；ordinal≠wire；不与 0F/参数35 电机位等同。
- 2C：既有单字节窄化/ACK 证据仍有效；八段仍无外部业务入口或恢复路径。
- 0A：两种 10 字节布局证据仍有效；类外调用仍仅 DT501 UVC，不在当前相机排除范围外开放；无 HG724 0A 路径。
- 01/07：三类目标均无定义、无外部调用、无枚举外引用。

负面检索不是固件不支持证明。

## 复现

```sh
PYTHONPATH=work/research/analysis-venv/lib/python3.*/site-packages:tools/research \
  work/research/analysis-venv/bin/python tools/research/ronin_gap_prefix_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/prefix-restored-final-b \
  --output work/research/gap-prefix-reproduced.json
python3 -m unittest discover -s tools/research -p test_ronin_gap_prefix_trace.py -v
```
