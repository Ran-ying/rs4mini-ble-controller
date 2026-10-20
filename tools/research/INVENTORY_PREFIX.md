# 全清单与设备管理缺口（八段复核）

2026-10-20；运行时 0.7.33 / 0.3.33。工具 [ronin_inventory_prefix_trace.py](ronin_inventory_prefix_trace.py)，证据 [ronin-inventory-prefix-evidence.json](../../protocol/research/ronin-inventory-prefix-evidence.json)。

## 发现来源（live extraction）

工具从 **PREFIX bank05** 的 `CmdIdGimbal$CmdIdType.<clinit>` **现场解析**枚举构造参数（`constructor_records`），得到 name / ordinal / wire。  
[旧六段表](../../protocol/research/ronin-command-references.json) 仅作对比，**不是**本轮发现来源。

对每个非排除条目检查是否已出现在 `protocol/COMMANDS.json` 的 `04:xx` 键中：

- `newlyDiscoveredGimbalWireCommands` = 现场提取到、但 COMMANDS 中尚无对应键的非排除 wire（由提取结果计算，不是写死的空列表）。
- 当前 APK 提取 40 个非排除条目，该列表为空，表示 **“旧表中的那 40 个非排除枚举均已登记”**，**不是**全固件命令穷尽或 `inventoryComplete=true`。

另在八段上对线性 `SendPack`（cmdSet=GIMBAL）做语法扫描：已知枚举 wire 命中与 **枚举外** orphan 字面量分别计数；orphan 为空仍不是反射/native/动态路径已排除的证明。

排除相机/哨兵：`FocusControl`、`NotiFyCameraId`、`Other`。

`inventoryComplete` **保持 false**。

## 设备管理 / 激活

bank01 存在 `ActiveDeviceController` / `ActiveWebController`，并直接触达 `DataGimbalActiveStatus`、`DataCenterActiveStatus` 与 HTTP 激活 API。这是**设备管理缺口证据**，不是已建立的 HG724 BLE 激活/绑定协议，**不开放激活写入**。`00:32` CENTER 只读 GET 保持只读。

## 复现

```sh
PYTHONPATH=work/research/analysis-venv/lib/python3.*/site-packages:tools/research \
  work/research/analysis-venv/bin/python tools/research/ronin_inventory_prefix_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/prefix-restored-final-b \
  --output work/research/inventory-prefix-reproduced.json
python3 -m unittest discover -s tools/research -p test_ronin_inventory_prefix_trace.py -v
```
