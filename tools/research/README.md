# Ronin APK 静态研究工具

最新进展：[CODE_RESTORATION.md](CODE_RESTORATION.md) 记录当前 APK 内部代码备份的离线恢复，已读到 HG724 灵敏度 setter 和参数加载逻辑；下面原有工具仍是 metadata-only 视图。

此工具只读 ZIP/DEX 元数据，不安装或运行 APK，不使用 Frida、不连接设备。SDK 与默认测试不依赖可选分析库。
输入限定为已检查的 DJI Ronin 2.2.2/7096 APK（完整 SHA256 见 `ronin_static.py`）；不同文件会在生成输出前拒绝。
APK 从 [DJI 官方下载页](https://www.dji.com/downloads/djiapp/dji-ronin) 获取，不随仓库分发。

从仓库根目录执行，输出使用被忽略的 `work/`：

```sh
python3 tools/research/ronin_static.py --apk work/research/dji-ronin-2.2.2.apk --output work/research/ronin-static
```

标准库阶段按残留 map_list 定位 8 段隐藏 DEX，对可校验的 6 段重建分析用头部和 string_ids。
只在 128 KiB 后字符串索引全部匹配时重建受损前缀；其余两段明确保留为不可结构化读取。
输出 DEX 是派生分析视图，**没有恢复被保护的原始方法体**，不作为原应用发布或执行。

可选方法/枚举分析需要 Python 3.10+ 和隔离的 Androguard 4.1.3 环境：

```sh
python3 -m venv work/ronin-analysis-env
work/ronin-analysis-env/bin/python -m pip install androguard==4.1.3
work/ronin-analysis-env/bin/python tools/research/ronin_static.py --apk work/research/dji-ronin-2.2.2.apk --output work/research/ronin-static --analyze
```

分析仅对构造函数中的常量赋值做符号追踪，不调用应用类；发现枚举分支时拒绝推断。
NOP/常量/返回模式只标记为保护桩候选，不把返回零解释成协议算法。
`evidence.json` 包含文件哈希、映射计数、枚举值、方法位置/哈希和参数资源索引冲突。
仓库仅保存筛选后的事实摘要，不保存 APK、派生 DEX、反汇编、完整参数资源或第三方库。

复核用 [DEX 格式](https://source.android.com/docs/core/runtime/dex-format) 和
[Dalvik 指令格式](https://source.android.com/docs/core/runtime/dalvik-bytecode)。SDK 参数候选解析的独立来源见 `docs/PROTOCOL.md`（从仓库根目录读取）。

## 官方 MSDK 交叉研究

[MSDK_V4.md](MSDK_V4.md) 记录官方 provided JAR 的只读提取方法、回中/参数/手柄候选布局和跨型号差异。
`msdk_static.py` 与 `msdk_payloads.py` 只用于离线研究；没有新增 SDK 发送能力或高级功能。

## 当前 App 型号追踪

[HG724.md](HG724.md) 记录 RS 4 Mini 展示名/蓝牙前缀的真实指令关联、专属设备类与参数资源原名。
`ronin_model_trace.py` 只读固定 APK；身份识别与完整命令分支分开记录，不改变 SDK 发送能力。


## 命令方法审计与当前 SDK

`ronin_command_audit.py` 对固定恢复视图校验SHA256，输出55类/631方法的哈希、位置和命令枚举引用，不输出完整厂商指令体、不执行代码。可选依赖仍为Androguard4.1.3，复现命令与新参数SDK边界见 [APP_COMMANDS.md](../../docs/APP_COMMANDS.md)。默认测试不导入可选分析依赖。
