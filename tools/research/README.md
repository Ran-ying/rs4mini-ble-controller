# Ronin APK 静态研究工具

当前统一入口：[研究方法与推进路线](../../docs/RESEARCH_ROADMAP.md)。八段具名恢复以 [PREFIX_RESTORATION.md](PREFIX_RESTORATION.md) 为准；下面各批记录保留其当时范围，不代表当前仍只有元数据或六段视图。

保存命令八段重审：[SAVE_PREFIX.md](SAVE_PREFIX.md)，工具 `ronin_save_prefix_trace.py`；历史六段见 [SAVE_CALLERS.md](SAVE_CALLERS.md)。仍不开放 saveSettings。

0D/2C/0A 八段缺口重审：[GAP_PREFIX.md](GAP_PREFIX.md)。

14/0C/4C 八段运动重审：[MOTION_PREFIX.md](MOTION_PREFIX.md)。
04:14 rotate→pause/EYE→transport 端到端：[ROTATE_EYE_TRANSPORT.md](ROTATE_EYE_TRANSPORT.md)。
离线队列 A 语义耗尽：[QUEUE_A_SEMANTICS.md](QUEUE_A_SEMANTICS.md)。
离线队列 B 参考系：[QUEUE_B_REFERENCE_FRAME.md](QUEUE_B_REFERENCE_FRAME.md)。

程序 25/37/62/63 八段重审：[PROGRAM_PREFIX.md](PROGRAM_PREFIX.md)。

全清单/设备管理八段复核：[INVENTORY_PREFIX.md](INVENTORY_PREFIX.md)。

早期代码恢复进展：[CODE_RESTORATION.md](CODE_RESTORATION.md) 记录当前 APK 内部代码备份的离线恢复，已读到 HG724 灵敏度 setter 和参数加载逻辑；下面原有工具仍是 metadata-only 视图。

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


`ronin_settings_trace.py` 补充八个继承setter的掩码/分支极性、命名键和两条参数记录，固定恢复与APK哈希。重现步骤与SDK契约见 [APP_SETTINGS.md](../../docs/APP_SETTINGS.md)。不输出完整指令体，不执行厂商代码，不推断本机支持。


`ronin_calibration_trace.py` 校验固定APK/恢复视图，记录HG702覆盖的无ACK调参请求、状态枚举和16个方法指纹。复现和边界见 [APP_CALIBRATION.md](../../docs/APP_CALIBRATION.md)，不执行厂商代码或操作硬件。


`ronin_motor_trace.py`固定命名电机参数的31/32空间、12条记录、26个方法指纹与INT08U实际编码路径，来源与复现见 [APP_MOTOR_TUNING.md](../../docs/APP_MOTOR_TUNING.md)。继承不代表型号固件支持，源范围不是机械安全保证。

平衡测试新增静态证据：[调用链与同名参数冲突](BALANCE_TEST.md)。运行时版本未变，尚未新增该SDK接口或硬件验收。

自动校准system_calc的固定哈希、命名数组槽、资源及14方法指纹复现工具为 `ronin_system_calibration_trace.py`；说明与未验收边界见 [APP_SYSTEM_CALIBRATION.md](../../docs/APP_SYSTEM_CALIBRATION.md)。不执行厂商代码。


多段恢复续报：已严格恢复6段49,542条code_item，原business05哈希不变；另外2段未恢复，模式UI语义仍需核对。见 [CODE_BANKS.md](CODE_BANKS.md)。运行时保持0.7.8/0.3.8，无新增发送或硬件操作。

跟随/RC档位的SDK与UI跨段复现工具为ronin_follow_modes_trace.py，六条命名记录、轴移位、枚举与18方法指纹；说明见 [APP_FOLLOW_MODES.md](../../docs/APP_FOLLOW_MODES.md)。


数值参数静态续报：[普通18项与独立配置分支](NUMERIC_PARAMS.md)。已核对有效继承、缺省读取模型及1/2字节编码，独立配置由App与输入源2同包写入。本批尚未新增这些SDK接口，运行时保持0.7.9/0.3.9。

COMMON00:32接收审计：[ACTIVATION_RECEIVE.md](ACTIVATION_RECEIVE.md)，39方法核对基础表返回码、双分发/反射及共享缓存顺序；八段版本查询直接调用扫描不证明HG724入口，SDK收发未开放。

后续[GET/旧推送/V13/V14格式审计](ACTIVATION_FORMATS.md)固定34方法，保留SN转换及长度语义并隔离源自动回复；仍不是HG724协议或激活流程完成证明。

后续[HG724入口审计](ACTIVATION_ENTRY.md)定位继承序列号GET为CENTER/id7，并确认通用V13/V14默认模块8的条件门槛；补充源码路由，不代表实际会话/设备或完整激活流程已验收。
