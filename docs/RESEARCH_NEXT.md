# 剩余非相机协议的静态研究记录

2026-10-15。在完成 0.7.0 扩展后，继续检查 [DJI 官方 Ronin 下载页](https://www.dji.com/downloads/djiapp/dji-ronin) 提供的 Android 文件。
下载文件名标为 2.2.2 / 7096，SHA256：

`4ef0aa1e351990168a522500728790e22794618b0bcbd4c6277c7375148dc4f4`

未安装、未运行 APK，也没有接触稳定器。文件和临时解析脚本在被忽略的 `work/research/`；不放入源码包或 Git。

## 已观察到的线索

- `classes.dex` 长 69,867,108 字节，标准头部字符串池只有 346 项，含 `com/AppGuard/AppGuard` 壳类。
- 尾部 `dexdata0` 业务负载仍能找到下列类名，但正常头部并未暴露这些类的完整方法/字段表。
- 原生 `libgimbal-lib.so` 中检查到的是跟踪控制相关符号，没有据此推导稳定器非相机参数。

可继续定位的业务类：

| 目标 | 类名线索（`dji.midware.data.model.P3`） |
|---|---|
| 原生绝对角/速率 | `DataGimbalAbsAngleControl`、`DataGimbalAngleControl` |
| 单轴重置/模式 | `DataGimbalNewResetAndSetMode` |
| Ronin 用户参数 | `DataGimbalRoninGetUserParams`、`DataGimbalRoninSetUserParams`，后者有 `WorkMode` / `HoldType` 嵌套类 |
| 校准/进度 | `DataGimbalCalibrate`、`DataGimbalAutoCalibration`、`DataGimbalGetPushCalibrationStatus` |
| 平衡状态 | `DataGimbalBalanceAdjust`、`DataGimbalGetBalanceAdjustPushInfo` |
| 额外反馈/电量 | `DataGimbalGetPushUserParams`、`DataGimbalPushBatteryInfo` |
| 原生动作程序 | `DataGimbalSetDelayTimelapseParams`、`DataGimbalGetPushTimelapseStatus`、`DataGimbalGetPushPanoramaStatus` |

这些只是应用包含的共同类名，**不能证明 RS 4 Mini 会走对应路径，也不能据此填入命令 ID、字段偏移或枚举值**。
目前没有完成业务负载的结构还原，没有提取到可直接采用的 RS 4 Mini 参数表。因此本轮不扩大已列明的实验命令允许列表。

## 下一步证据

继续静态还原时，需要同时证明请求构造、响应解析和 RS 4 Mini 的型号分支。仅恢复字符串或使用无人机/Osmo 的同名类不足以确认。
现场条件具备后，可在 Ronin App 中一次只改变一个非相机设置，记录前后屏幕状态与受控 BLE 样本，匹配这些候选类和 DUML 字段。
不得批量探测、重放校准或恢复默认参数命令。采样与运动仍遵循 `HARDWARE_CHECKLIST.md`。

## 2026-10-16 命令覆盖复核

公开来源复核仍未建立 RS 4 Mini 全部非相机 BLE 命令的型号专属枚举。
另有 [dji-gimbal-ble 协议研究](https://github.com/malt4010/dji-gimbal-ble/blob/main/DJI_PROTOCOL.md)，其标识为 OSMO；
没有据此移植模式/参数枚举，也未扩大本机已验证命令的声明。
已将项目已用命令、请求/响应解析程度和未知功能分别登记在 `SDK_COMMANDS.md` 和 `../protocol/COMMANDS.json`。
硬件不可用期间，静态类名与跨型号示例不能补足本机验证；新增高级功能继续受底层验收条件约束。

## 2026-10-16 深入静态恢复结果（0.7.2）

- 找到 8 组隐藏业务 DEX 的 `map_list`，其中 6 组可用未损坏的字符串索引后缀验证物理顺序。
  损坏集中在每段最前 128 KiB；重建头部和 string_ids 后，这 6 段的类型/方法索引引用检查无越界。
- 对 6 段进行元数据结构化读取；并未恢复保护层保存的原始方法代码。抽查 98 个相关方法，74 个呈现
  NOP/常量/返回保护桩模式。模式、Ronin 参数读写和版本解析等关键方法不能据此还原请求/响应。
- `CmdIdGimbal$CmdIdType.<clinit>` 未被清空：43 个枚举项、42 个 byte 范围项、41 个不同 byte 编号。
  `SetAngle` 与 `AngleControl` 同为 0A；`Other=511` 是哨兵，不能截断成一个可发送命令。
  `FocusControl` 和 `NotiFyCameraId` 标记为排除的相机范围，不开放调用。
- 发现原先资源名混淆的 `res/DB.json`（106 条）与 `res/jy.json`（33 条）参数描述。
  同一资源内同一 index 也可重复：DB 中 35 对应 `shut_down_motor` 和 `motor_special_cmd`；
  不同表的范围也不同。不能用线上的索引直接推断唯一名称、类型、固件参数或安全值。
- 工作模式和握持类型枚举可读，但缺少 RS 4 Mini 型号分支与有效打包代码，不能把它们当成
  PF/PTF/FPV 或本机设置命令。候选编号如 04:31/32（Ronin 参数）、04:35/36（手柄参数）、
  04:62/63（Track/Panorama）只登记为候选，不加入发送允许列表。

可复核工具与方法见 `../tools/research/README.md`；派生事实、代码位置和哈希见
`../protocol/research/ronin-2.2.2-evidence.json`。原始 APK、完整资源、反汇编和依赖仍在忽略目录。

SDK 本轮只补充 04:10 参数响应和 04:0F 单字节 ACK 的被动候选结构解析，来源是旧 DUML
解码器，另由 RS 3 的 `12 → 00120100` 样本印证。返回索引/长度/原始值或逐项错误，不映射名称，
不解释数值类型，不主动查询，不发送任何新命令。所有结果仍带 `deviceVerified:false`。
下一步仍需恢复保护方法、型号路径或获取受控本机证据；全命令前置条件保持未满足。


## 2026-10-16 官方 MSDK 静态交叉研究（运行时版本未变）

从 DJI 官方声明的 Maven 坐标检查 provided 4.18 JAR，固定哈希与 Maven SHA1 均已核验。
9 个目标类能直接读取 classfile；不少方法在提前返回后保留候选逻辑，原样保存指令和返回前缀，未执行或修改厂商代码。

- 04:4C 获得两字节候选布局与旧版模式/回中枚举，但旧 YAW_CENTER=1 和本机 FE01 三轴回中存在语义差异；
  当前 Ronin 同名类是布尔 reset 字段，不能开放按轴/模式写入。
- 04:32 获得原始参数索引列表请求与依赖请求上下文/外部宽度的响应业务体候选；不自动映射参数名。
- 接收包尾部存在按响应位和命令配置剥离返回码的分支，因此业务方法的 offset 0 不能直接等同 BLE payload offset 0。
- 04:35/36 获得 8 字节手柄参数候选及前五项原始读取偏移，缺少本机字段语义/有效范围。

可复现工具、静态方法指纹与离线核对载荷见 [研究说明](../tools/research/MSDK_V4.md) 和
[事实记录](../protocol/research/msdk-4.18-evidence.json)。这些不是新设备支持；命令清单仍为 48 条，全部命令门槛未通过。
新工具不被 SDK 或 UI 引用，没有发送接口。SDK/面板版本保持 0.7.2/0.3.2，既有安装包继续对应原交付提交。


## HG724 型号与参数资源关联（2026-10-16）

可读 App 指令已把展示名 DJI RS 4 Mini 与 BLE 前缀 dji rs4 mini- 关联到 HG724。
HG724 类型枚举值 103 仅为 App 事实，不是已解码线上字段或本机查询结果。
专属类注册 FollowModeSensitivity，但设置方法与参数加载仍为保护桩，未恢复具体命令/索引/载荷。
两份资源原名分别为 gimbal_param_infos（res/DB.json）和 ronin2_gimbal_param_infos（res/jy.json），
不能据资源名或继承关系认定本机采用哪一份。完整证据与复现见 [HG724.md](../tools/research/HG724.md)。
本轮只增加离线研究工具，SDK/原生版本、48 条清单及完整性门槛不变，没有硬件操作。


## 当前 App 原代码备份恢复（2026-10-16）

在 classes6/business-05 的 fdex/dgc2 尾部发现原始代码备份，19,436 条记录逐一匹配方法 code_off 槽位、完整长度和指令单元数，恢复为不执行的离线视图。
HG724 跟随灵敏度 setter、参数管理器读取 gimbal_param_infos 的路径及参数写入打包已可读：命名参数 cmd_follow_mode_sensitivity 为 index150/size1，04:0F 源码载荷为 960100 或 960101。
当前复位命令确认是 mode+布尔 reset，而非旧 SDK 按轴枚举。本轮只添加恢复与离线核对工具，未新增 SDK/UI 发送或解码接口，也没有操作硬件；整个协议和本机验收仍未完成。
复现、指纹、适用范围与剩余缺口见 [CODE_RESTORATION.md](../tools/research/CODE_RESTORATION.md)。此前“setter/加载仅见保护桩”的记录属于旧 metadata-only 阶段。


## 平衡测试静态调用链补充

HG724继承的启动路径为普通用户参数04:0F，balance_test/index37/size1，启动值64；不是直接调用04:40。资源存在两条同名参数范围0..1和0..255，加载器按顺序名称覆盖，不能取第一条或假定名称唯一。状态/三轴结果位已定位，零结果字段不能当作通过。详见 [BALANCE_TEST.md](../tools/research/BALANCE_TEST.md)。本批是静态证据与复现工具，未新增SDK接口、发送或硬件证据；运行时仍0.7.6/0.3.6，两个完成门槛仍false。


## 多段代码恢复续报

严格恢复固定APK6段49,542条原code_item，原business05哈希保持一致；2段仍缺可靠元数据，未恢复。新增40个模式键UI调用方指纹，可继续核对两位字段打包与型号分支。研究48项在Python3.8/3.12通过，实际独立目录复现一致；无SDK发送扩大、硬件/UI或厂商代码执行。运行时仍0.7.8/0.3.8，全协议/高级门槛false。见 [CODE_BANKS.md](../tools/research/CODE_BANKS.md)。


## 数值参数与输入源分支续报

18项普通跟随/RC数值已核对有效继承、命名映射、缺省读取模型及INT08U/INT16U两条单项/数组打包分支；另6项独立配置在App与输入源2同包写入，不能按名称相似自动替换。42方法指纹实际固定APK复现一致；研究53项在Python3.8/3.12通过，无新增SDK发送或硬件/UI操作。运行时仍0.7.9/0.3.9，全协议和高级门槛false。见 [NUMERIC_PARAMS.md](../tools/research/NUMERIC_PARAMS.md)。


2026-10-17预设研究新增26个方法指纹：UserProfile/table_choice、MovementSettingsProfile和GimbalWorkMode分别核对；HG724条件新模式列表为FPV/Custom/3D Roll 360，不能照搬旧PF/PTF位置。业务getPresetID偏移2尚未证明原始BLE偏移，SDK不解码为活动预设。见 [PROFILES.md](../tools/research/PROFILES.md)。运行时仍0.7.11/0.3.11，未新增接口或操作硬件，全命令门槛false。
