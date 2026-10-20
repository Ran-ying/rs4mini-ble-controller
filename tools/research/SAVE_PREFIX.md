# 保存命令八段 PREFIX_BANKS 引用重审

2026-10-20；运行时保持 Node/Python/Web 0.7.33、macOS 0.3.33。工具 [ronin_save_prefix_trace.py](ronin_save_prefix_trace.py)，证据 [ronin-save-prefix-callers-evidence.json](../../protocol/research/ronin-save-prefix-callers-evidence.json)。历史六段扫描见 [SAVE_CALLERS.md](SAVE_CALLERS.md)，不得改文字冒充本轮结果。

不执行 APK/Java/JNI/原生库/UI，不构造 DUML，不开放 `saveSettings`，不把 0F/31 写入或 13 恢复设置等同持久化。

## 方法

固定 Ronin 2.2.2/7096 APK 与八段 `business-XX-prefix-code-restored.dex` 的 `PREFIX_BANKS` 哈希全部核对后才加载 Androguard。逐段遍历带 code 的方法与指令，按实际操作分类：

- `external-direct-invoke` / `internal-invoke`
- `allocation` / `class-literal` / `field-reference`
- `enum-registration`（枚举字段 `sput-object`）/ `command-enum-reference`
- `string-literal-not-proven-reflection` / `other-reference`

字符串、字段类型、分配、class 常量与枚举注册**不算**外部直接调用。独立提取两次结果逐字节一致。

## 计数

| bank | 方法数 | 带 code | 指令数 | 保存引用方法数 |
|---|---:|---:|---:|---:|
| 00 | 53828 | 50517 | 682926 | 0 |
| 01 | 12143 | 11452 | 132775 | 0 |
| 02 | 15931 | 15446 | 249001 | 0 |
| 03 | 38674 | 36349 | 559947 | 0 |
| 04 | 56720 | 53246 | 587995 | 0 |
| 05 | 55055 | 53173 | 677878 | 4 |
| 06 | 48024 | 45737 | 705675 | 0 |
| 07 | 3240 | 2977 | 36394 | 0 |

八段合计 283615 方法、268897 带 code、3632591 指令（逐段之和，未跨段去重）。**新增 01/07 均无保存相关指令或字符串表命中。**

四个命中方法均在 bank05：`CmdIdGimbal$CmdIdType` 的 `$values`/`<clinit>`，以及 `DataGimbalSaveUserParams` 的 `getInstance`/`start`。引用种类含内部 invoke、自身分配/字段、枚举注册与枚举读取、字符串名；**外部直接调用=0，外部分配=0，无 HG724 抽象类提及。**

## 源包层（仍非持久化证明）

- `doPack()` 为空 `return-void`。
- `start(callback)`：APP→GIMBAL、REQUEST、NEEDACK.YES、业务 Encrypt.NO、CmdSet.GIMBAL、枚举 `SaveUserParams`；最终传输加密未验收。
- 枚举 `<clinit>` 以三参 `(String,I,I)` 注册 **wire commandId=17**，**不绑定** `Ljava/lang/Class;`；请求类单独存在，与 `GetUserParams` 的带 Class 六参构造不同。

空体+ACK+枚举定义只证明类能构造请求；没有 HG724 业务调用链或固件持久化路径，故不开放 SDK 保存接口。

## 复现

```sh
PYTHONPATH=work/research/analysis-venv/lib/python3.*/site-packages:tools/research \
  work/research/analysis-venv/bin/python tools/research/ronin_save_prefix_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/prefix-restored-final-b \
  --output work/research/save-prefix-reproduced.json
python3 -m unittest discover -s tools/research -p test_ronin_save_prefix_trace.py -v
```

证据中 `hg724BusinessEntryEstablished` / `persistencePathEstablished` / `saveSettingsOpened` / `targetDeviceVerified` 等均为 false。命令清单已关联本证据并保留 04:11 缺口。
