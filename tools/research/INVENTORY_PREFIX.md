# 全清单与设备管理缺口（八段复核）

2026-10-20；运行时 0.7.33 / 0.3.33。工具 [ronin_inventory_prefix_trace.py](ronin_inventory_prefix_trace.py)，证据 [ronin-inventory-prefix-evidence.json](../../protocol/research/ronin-inventory-prefix-evidence.json)。

## 清单

对照固定 [ronin-command-references.json](../../protocol/research/ronin-command-references.json) 的 40 个非排除 CmdIdGimbal 枚举：全部已出现在 `protocol/COMMANDS.json` 的 `04:xx` 键中。八段 PREFIX 扫描**未发现新的云台 wire ID**。排除相机/哨兵：`FocusControl`、`NotiFyCameraId`、`Other`。

`inventoryComplete` **保持 false**：仍有 `requestCodec=unknown` 且无实现的条目（含 0A/0D/11/25/2C/37/40/62/63 等），会话版本、设备身份、状态关联与本机验收未完成。不能把静态覆盖写成清单完成。

## 设备管理 / 激活

bank01 存在 `ActiveDeviceController` / `ActiveWebController`，并直接触达 `DataGimbalActiveStatus`、`DataCenterActiveStatus` 与 HTTP 激活 API。这是**设备管理缺口证据**，不是已建立的 HG724 BLE 激活/绑定协议，**不开放激活写入**。`00:32` CENTER 只读 GET 保持只读，不升级为激活、绑定或版本协商。

## 复现

```sh
PYTHONPATH=work/research/analysis-venv/lib/python3.*/site-packages:tools/research \
  work/research/analysis-venv/bin/python tools/research/ronin_inventory_prefix_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/prefix-restored-final-b \
  --output work/research/inventory-prefix-reproduced.json
python3 -m unittest discover -s tools/research -p test_ronin_inventory_prefix_trace.py -v
```
