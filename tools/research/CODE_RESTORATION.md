# 当前 Ronin App 原代码备份的离线恢复

2026-10-16。本轮发现并验证了新的代码来源，推进了之前卡在 NOP 保护桩的研究。
**这是离线恢复代码字节，不是运行/解包中的 App，不执行恢复后的 DEX。** SDK/原生版本仍为 0.7.2/0.3.2。

## 发现与验证

固定 Ronin 2.2.2/7096 APK 的隐藏 DEX 末尾存在 `fdex` 容器标记。对 business-05（原 classes6）的
尾部检查发现名为 `classes6.dex.dgc2` 的代码银行，头部/记录用大端，外部包装部分用小端。
记录包含数据偏移、长度、两个未解释字及原 encoded_method 中 code_off 的 ULEB 槽位。

这里的代码备份是可直接读取的 code_item 字节，没有执行加密器、解密器、JNI、虚拟机或 App。

- 19,436 条记录全部唯一对应到实际 encoded_method 的 **code_off 字段槽位**，不是只匹配方法名称。
- 原副本与备份的完整 code_item 长度、指令单元数匹配；检查对齐、边界、异常表/catch 地址、类型索引、handler 引用和目标区间不重叠。
- 标准库恢复器的最终 DEX SHA256 与独立 Androguard 辅助恢复结果相同：
  `4fdbd74a05df63d72a0feb1c907d9395426ec3cdb5d6aeb45e3836d856d66654`。
- 当前只恢复 business-05 的代码。原有元数据恢复仍有 2 段不可结构化读取，其他代码银行没有在本工具中恢复；不能声称整个 App 或全部协议已经恢复。
- 指纹分析抽取 26 个相关方法；其中 17 个先前为保护桩候选，恢复后不再呈该模式。代码恢复不等于实机验证。

APK、代码银行、恢复 DEX 和完整反汇编均留在忽略目录。仓库仅提交第一方解析工具、合成测试、精选方法指纹/引用和人工核对的协议事实。

## 已恢复的一条 HG724 静态链

已有展示名与 BLE 前缀将 RS 4 Mini 关联为 HG724。恢复后的工厂方法包含 HG724 专属类分支，
该类的 `setFollowModeSensitivity()` 明确使用以下路径：

`FollowModeSensitivity` → `CMD_FOLLOW_MODE_SENSITIVITY` → 名字 `cmd_follow_mode_sensitivity`
→ `DataGimbalSetUserParams.setInfo(name, value)` → `04:0F`。

参数管理器的加载线程明确读取资源 `gimbal_param_infos`，即 `res/DB.json`，按 **参数名字** 放入 map。
该名字的记录为 index=150（0x96）、size=1。与只靠线上 index 猜名字不同，这里同时有 setter、
常量名字、加载逻辑和命名记录的交叉证据。其他参数的全局 index 冲突仍存在，不生成通用反向名称映射。

模式枚举 DEFAULT_MODE=0、SENSITIVITY_MODE=1；App 输入等于 1 时写 1，其他整数归一为 0。
离线工具只接受显式 0/1，拒绝隐式纠正输入。

| 内容 | 由代码导出的 payload | 边界 |
|---|---|---|
| 灵敏度默认模式，04:0F | `96 01 00` | 没有发送，也未开放 SDK 写入 |
| 灵敏度敏感模式，04:0F | `96 01 01` | 无物理速度/跟随效果保证 |
| 读取该参数的 04:10 索引体 | `96` | 来自通用 GetUserParams 编码，不等于观察到此 setter 主动发起读取 |

这些只是 payload，不包含 DUML 帧、序号、标志和 ACK 清理；后者仍要逐项审计。
跟随灵敏度不是 PF/PTF/FPV 跟随轴模式，不能据此宣布全部模式实现。

## 当前复位布局

恢复的 `DataGimbalNewResetAndSetMode.doPack()` 确认：第 0 字节为 mode 值，第 1 字节为
`resetGimbal` 布尔值 0/1。它没有旧 MSDK ReturnCenterCmd 按轴枚举，进一步解释了此前语义差异。
`FE01` 对应保留模式值加复位；不据此开放 `FE04`，也不认为该命令包含真正单轴回中功能。

## 响应与高索引边界

本轮离线响应工具只核对已显式分离状态字节的业务体 `96 01 rawValue`，未知值保留原始字节。
索引 150 是无符号参数索引，不能走旧 DUML 的负 int8 错误码解释。现有 `rs3/rs3mini` 候选解码器未改变，
不能把它直接套到当前 App 参数响应。返回码、帧条件与真正设备响应仍待完整验证。

## 复现

标准库恢复，不需要 Android、Java 或 Androguard：

```sh
python3 tools/research/ronin_code_restore.py --apk work/research/dji-ronin-2.2.2.apk --output work/research/ronin-code
```

可选 Androguard 4.1.3 方法指纹（隔离环境同 [README.md](README.md)）：

```sh
python tools/research/ronin_code_restore.py --apk work/research/dji-ronin-2.2.2.apk --output work/research/ronin-code --analyze
python -m unittest discover -s tools/research -v
```

原始 APK 在任何输出前核对完整 SHA256；不匹配即拒绝。恢复只改变忽略目录中的分析副本，并重算该视图的 DEX 校验字段；
不修改原 APK，不生成安装包。标准库边界解析依据沿用 [DEX 格式](https://source.android.com/docs/core/runtime/dex-format)。
仓库证据为 `protocol/research/ronin-code-restoration-evidence.json`；旧 metadata-only 证据保留为历史阶段，不能误读成当前恢复器仍只能看到保护桩。

`ronin_app_payloads.py` 是纯离线、无传输的源代码载荷核对工具，不被 SDK/UI 引用。全部设备命令的请求、响应、停止和本机验收尚未完成；
`inventoryComplete` 与新增高级开发条件保持 false，未操作硬件。


多段恢复续报：已严格恢复6段49,542条code_item，原business05哈希不变；另外2段未恢复，模式UI语义仍需核对。见 [CODE_BANKS.md](CODE_BANKS.md)。运行时保持0.7.8/0.3.8，无新增发送或硬件操作。
