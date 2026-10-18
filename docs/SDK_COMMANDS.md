# 设备 SDK 命令审计与高级开发前置条件

2026-10-19，0.7.32 / 原生 0.3.32。**尚不能确认 RS 4 Mini 全部非相机 BLE 命令都已枚举、解析并封装。**
机器清单是 [protocol/COMMANDS.json](../protocol/COMMANDS.json)，目前记录 48 个命令或缺口条目；
它不是厂商完整命令表，不能以“所有已知代码已封装”代替“所有设备命令已知”。

用户指定的顺序：两层拆分 → 底层全部范围内命令解析/封装验收 → 继续新增高级功能。
第一步已实施；第二步未完成，因此第三步暂停。现有高级功能保留并回归。

## 审计结果

`implemented` 表示已有请求编码/受控发送实现，不代表型号兼容或物理效果确认。
`partial` 表示仅部分字段/操作已明确；`raw` 表示只提供原始消息，不等于业务字段已解析。
`hardware` 仅表示存在本机历史观测，具体覆盖看最后一列和 `VALIDATION.md`；
`other-model`、`official-app-enum` 和 `none` 不得提升为本机支持。
`app-generic-code` 表示当前App通用类字段已核对，尚无目标型号布局/调用证据，默认仅提供明确标注的被动候选解码；已审计发送例外限于6B固定type0/1状态推送启停和type2单次状态请求，显式来源且不代表本机支持；没有自动订阅维护或程序执行。
`candidate-structured` 仅指有来源的候选结构解析，不能计作本机业务字段验证。通知没有请求，记为 `not-applicable`。

| 命令/缺口 | 内容 | 请求封装 / 响应解析 | 设备证据 | 尚缺什么 |
|---|---|---|---|---|
| `00:01` | 版本查询 | `implemented` / `raw` | `other-model` | 响应返回原始消息，型号/版本字段未确认 |
| `04:01` | 虚拟摇杆及中位停止 | `implemented` / `not-applicable` | `hardware` | 历史设备行为已验证，无固件执行确认 |
| `04:02` | 位置查询 | `implemented` / `raw` | `other-model` | 本机历史尝试未收到有效响应，不能判断不支持 |
| `04:05` | 姿态与关节通知 | `not-applicable` / `partial` | `hardware` | 姿态/关节映射已确认；四元数顺序及部分标志未知 |
| `04:08` | HG724来源AUTO部件校准候选 | implemented / candidate-structured | app-code-path | 0.7.30新鲜35电机门槛后发00，独占到关联ACK；不开放其他部件，实际会话/本机/物理完成/中止待验收，见APP_COMPONENT_CALIBRATION.md |
| `04:0B` | 控制状态查询 | `implemented` / `raw` | `other-model` | 响应字段未确认 |
| `04:0C` | 原生速率候选 | `implemented` / `unknown` | `other-model` | 轴序/单位/释放仅有 RS 3 来源，本机未验证 |
| `04:0F` | 用户参数写入与旧休眠候选 | `implemented` / `partial` | `app-code-path` | 当前App配置封装灵敏度、两组位设置、平衡/系统校准请求、六组按轴档位读改写及ACK；非任意参数写入。PF/PTF、其余字段、持久化与本机效果未验收，旧休眠仍为其他型号来源；0.7.10新增18项普通命名数值的1/2字节读写和异常原值保留，不自动切预设/输入源，活动预设与实际效果未验收 |
| `04:14` | 原生绝对角候选 | `implemented` / `unknown` | `other-model` | 当前App继承rotate的8字节体/时间缩放已核对；既有接口仍仅其他型号实验配置，初始化能力与静态地址链已核对；动态能力/本机地址/EYE依赖与恢复、参考系和完成/中止语义仍待验收 |
| `04:1C` | 设备类型查询 | `implemented` / `raw` | `other-model` | 已在 App 可读代码中关联 RS 4 Mini=HG724，类型枚举值 103；线上偏移、返回码及本机响应未确认，仍返回原始消息 |
| `04:1E` | degree-info 请求 | `implemented` / `raw` | `hardware` | requestDegreeInfo 封装关联原始响应；本机历史 00 不等于完整字段解析或增频确认 |
| `04:30` | App传感器校准候选与旧型号实验 | not-applicable / candidate-structured | app-generic-code | 0.7.28当前App被动状态0/1/3/9、进度/尾部保留；不复用旧bool/08表，无触发/查询/订阅/ACK，本机/单位/请求关联待验收 |
| `04:4C` | 重置/模式命令中的三轴回中 | `partial` / `unknown` | `hardware` | 当前 App 的原代码备份确认两字节 mode+布尔reset；本机仍只确认 FE01 三轴回中，无按轴选择位，旧 MSDK 轴枚举不可套用；其他模式/响应待本机证据 |
| `04:66` | 外设状态源候选与旧型号原始TLV | `not-applicable` / `candidate-structured` | `app-generic-code` | 0.7.25显式App来源46类型/43视图，碰撞/GPS截断保留；无发送或姿态/关节重映射，本机未验收 |
| `0D:02` | 电量候选通知 | `not-applicable` / `partial` | `other-model` | 百分比仅为其他 Mini 研究格式，本机未证实 |
| `unknown:follow-mode` | 跟随模式与手柄参数 | `unknown` / `unknown` | `app-code-path` | 灵敏度、自定义跟随轴、六组按轴档位及18项普通跟随/RC数值已封装；PF/PTF/FPV完整预设、活动custom预设验证、独立配置真实效果、低两位及型号/本机效果仍待完成 |
| `unknown:motor-calibration` | 电机参数/自动整定/水平校准 | `unknown` / `unknown` | `none` | 自动调参请求/状态、十二个电机数值、平衡测试及system_calc自动校准请求/状态已封装；system_calc与水平校准的型号/UI身份仍未确认；其他字段、实机接受/效果/持久化和固件中止仍待完成 |
| `unknown:firmware-program` | 固件动作程序 | `unknown` / `unknown` | `none` | 七个通用程序/状态类、106方法指纹、60类外直接调用已审计；已区分三种路点/计数和源ACK/订阅，HG724路径、完整单位/范围、程序关联及执行/取消/通知仍待审计封装 |
| `unknown:device-management` | 激活/绑定/恢复设置/固件管理的 BLE 覆盖 | `unknown` / `unknown` | `none` | 是否通过本 BLE 链路提供及其协议尚未枚举；连接成功不证明设备管理命令已全覆盖 |
| `04:07` | Pitch/Roll微调请求 | `implemented` / `partial` | `app-code-path` | 0.7.14源码float32参数/轴值2与0、独占到ACK；实际角度/累加/持久化/暂停状态与本机效果未验收，无Yaw或自动暂停/回滚 |
| `04:0A` | 官方 App 枚举：SetAngle | `unknown` / `unknown` | `official-app-enum` | 已区分两种10字节源布局，六段类外直接调用仅DT501 UVC，未定位HG724路径；未开放发送 |
| `04:0D` | SetOnOrOff枚举（用途未定） | `unknown` / `unknown` | `official-app-enum` | 六段仅枚举自身引用，无已识别出站候选/同名类；ordinal5不是wire0D，payload/HG724路径未知，不与参数35等同，不据零引用判不支持 |
| `04:10` | 当前 App 用户参数读取 | `implemented` / `partial` | `app-code-path` | 当前App配置按请求index/size读取，返回码、无符号索引和原始头字节分离；命名设置/状态/六组按轴档位已解码，未按索引推断其他字段，本机读数和更多参数仍待验收；0.7.10新增18项普通命名数值的1/2字节读写和异常原值保留，不自动切预设/输入源，活动预设与实际效果未验收 |
| `04:11` | 保存用户参数源类 | `unknown` / `unknown` | `official-app-enum` | 六段恢复视图仅4个内部/枚举引用方法，无外部直接调用者；1/7、保护桩、反射/固件路径未排除，未开放HG724保存SDK |
| `04:12` | 单次命名参数订阅请求 | implemented / not-applicable | app-code-path | 0.7.26固定源分支152键、非空单次、CENTER/id7无ACK；无自动刷新或远端停止，本机路由/通知未验收 |
| `04:13` | HG724恢复设置请求 | `implemented` / `partial` | `app-code-path` | 0.7.16显式来源分支010001与关联ACK；不重放/回滚，范围、生效、持久化及断线行为待实机验收 |
| `04:24` | 当前App通用固定参数通知 | `not-applicable` / `candidate-structured` | `app-generic-code` | 0.7.12被动解码17个源getter，完整已知布局不少于74字节、仅未加密请求型，未知字节/枚举保留；不触发订阅，本机布局/活动预设及更多字段仍未验收 |
| `04:25` | 官方 App 枚举：SetDelayTimelapseParams | `unknown` / `unknown` | `official-app-enum` | 当前App通用10字节点/最多6点、OR型info及外设位已静态核对；HG724调用、单位/范围、停止/相机隔离和本机效果未完成，未开放SDK发送 |
| `04:27` | 源异常状态被动候选 | `not-applicable` / `candidate-structured` | `app-generic-code` | 0.7.21显式App来源下21直接字段+Roll/Pitch OR复合，未知字节保留；与旧RS3 sleep候选分开，本机布局/语义未验收，不触发控制 |
| `04:2B` | 源教程状态被动候选 | not-applicable / candidate-structured | app-generic-code | 0.7.32原始步骤/32位状态/9数值标志/Java位移及尾部；未知源回退FINISH不当完成，无发送，本机布局/通知未验收 |
| `04:2C` | 教程步骤源候选 | unknown / unknown | official-app-enum | 通用单字节窄化与ACK已静态核对；HG724入口、作用及恢复未确认，未开放发送 |
| `04:31` | 命名电机参数写入 | `implemented` / `partial` | `app-code-path` | 显式当前App配置封装十二个命名电机字段的单项写入/ACK与按上下文读取，和0F/10空间分开；源范围不是机械安全保证，实际生效/持久化/型号UI支持未实机验收；未开放任意参数写入 |
| `04:32` | 命名电机参数读取 | `implemented` / `partial` | `app-code-path` | 显式当前App配置封装十二个命名电机字段的单项写入/ACK与按上下文读取，和0F/10空间分开；源范围不是机械安全保证，实际生效/持久化/型号UI支持未实机验收；未开放任意参数写入 |
| `04:33` | 源电量被动候选 | `not-applicable` / `candidate-structured` | `app-generic-code` | 0.7.21显式App来源保留原始容量0..255及尾字节，不夹取或合并0D02；真实通知、本机布局与单位未验收 |
| `04:35` | 手柄单字段设置请求 | `implemented` / `partial` | `app-code-path` | 0.7.15显式App来源下三个命名字段0/1，未指定字节源默认FF；NACK直接失败，无缓存兜底/回读/保存/重放，FF含义及实际效果/持久化待本机验收 |
| `04:36` | 手柄参数只读查询 | `implemented` / `candidate-structured` | `app-code-path` | 0.7.13空体/关联ACK，8个业务字段原值与bit0、尾字节保留；源继承路径不代表本机布局/效果或预设关系确认 |
| `04:37` | 官方 App 枚举：SetTimelapseParams | `unknown` / `unknown` | `official-app-enum` | 另一版延时最多5点、mode=1两字节、总时长覆盖首点时长已核对；与25分开，HG724调用/字段单位/完成与停止未验收，未开放SDK发送 |
| `04:38` | 官方 App 枚举：GetPushTimelapseStatus | not-applicable / candidate-structured | app-generic-code | 0.7.22显式来源下被动4字节候选、状态mask3与原值/尾字节保留；不发源自动ACK，本机布局/状态与物理完成未验收 |
| `04:40` | 官方 App 枚举：BalanceAdjust | `unknown` / `unknown` | `official-app-enum` | 命令枚举已确认，具体方法/字段与HG724分支仍需逐项证据，不把枚举恢复等同请求体完成；未开放发送；HG724继承的startGimbalBalanceTest静态路径不直接调用此命令，而使用0F的命名参数；不能仅凭类名替代 |
| `04:6A` | HG702/HG724 自动调参请求（无ACK） | `implemented` / `not-applicable` | `app-code-path` | HG724继承HG702覆盖实现，00 01 bool请求且不请求ACK；仅声明本机发送，false请求的物理中止效果、运行中运动互斥和执行完成均未实机验收 |
| `04:62` | 官方 App 枚举：SetTrack | `unknown` / `unknown` | `official-app-enum` | 通用最多10点、Math.round/低16位与1字节停止候选及Create UI调用已核对；型号可达性、参考系、相机隔离与停止/完成未验收，未开放SDK发送 |
| `04:63` | 官方 App 枚举：SetPanorama | `unknown` / `unknown` | `official-app-enum` | 通用10字节混合宽度及Create UI调用已核对，含曝光/拍摄字段；型号、预览隔离和物理取消未验收，未开放SDK发送 |
| `04:64` | 官方 App 枚举：GetPushPanorama | not-applicable / candidate-structured | app-generic-code | 0.7.22显式来源下被动5字节候选、uint16计数与尾字节保留；不发源自动ACK，本机布局/通知与物理完成未验收 |
| `04:6B` | 官方 App 枚举：GetPushTrackAndTimelapse | implemented / candidate-structured | app-generic-code | 0.7.24封装显式type0/1推送启停和type2单次请求；ACK业务体不透明，不证明远端订阅状态或新通知。无自动维护/程序执行，本机布局、程序关联与物理效果未验收 |
| `04:6E` | 当前 App 校准状态查询/通知 | `implemented` / `partial` | `app-code-path` | 显式当前App配置下空体查询/ACK与被动TLV状态分别解析；未知字段保留，无记录不造零值；无程序ID关联，订阅/停止条件及本机通知待验收 |
| `04:69` | 外设数据源候选 | not-applicable / candidate-structured | app-generic-code | 0.7.27显式来源被动TLV/tag2原值；不发送/订阅/ACK，不继承旧速度。本机布局/单位/参考系未验收 |
| `04:57` | 源手柄状态被动候选 | `not-applicable` / `candidate-structured` | `app-generic-code` | 0.7.20显式App来源下解码两个signed short与两个源状态位，未知位/尾字节保留；无订阅/发送，本机布局、单位与轴映射未验收 |
| `04:58` | 手柄摇杆控制开关候选 | implemented / partial | app-code-path | 0.7.31显式bool00/01与严格ACK，尾部不透明保留；不更新57或自动订阅，实机效果/持久化/控制交互待验收 |

## 验收要求

1. 明确范围：RS 4 Mini 的非相机设备控制；固件版本与型号分支可追溯。相机和视觉继续按既定范围排除。激活/绑定/恢复设置/固件管理等若存在本 BLE 接口，也须审计，目前未枚举，不发送未知命令。
2. 命令枚举需要厂商完整 BLE 文档、可验证的型号业务分支或系统的受控 App 通信样本，
   当前没有这样的完整覆盖证据。第三方其他型号资料和候选类名不足以证明枚举齐全。
3. 每项分别提供请求字段/范围/单位/标志，响应字段/错误码，通知的启动与停止条件，
   请求关联、取消、超时和清理语义。未知保留原始量，不能猜枚举后宣称完成。
4. 完成可重复的离线向量与本机固件验收，记录实际模式/负载和停止效果。写入完成不等于设备执行。
5. 更新清单、协议与验收记录后，才把 `inventoryComplete` 和新增高级开发条件标为通过。
   当前两项明确为 false；分层检查验证这个状态与文件引用，不把协议缺口伪装成测试失败或已解决。

`04:1E` 本次只补齐受控请求/原始响应封装，未对硬件执行。四元数顺序、额外状态、固件模式、
参数与内置程序仍是研究任务，不能用上层组合替代底层验收。
所有硬件采样等待用户返回并明确要求测试；不批量探测未知指令。


历史0.7.2阶段的新增候选编号来自官方 App 的可读枚举，相关方法仍可能是保护桩；
48 条清单不是新增 48 项设备支持。详细证据见 `RESEARCH_NEXT.md` 与 `protocol/research/ronin-2.2.2-evidence.json`（仓库根目录）。
参数被动解析没有扩大任何发送允许列表，也没有解除高级功能前置条件。


进一步的官方 MSDK 交叉研究仅增加离线候选结构：04:4C 的旧轴枚举与本机回中语义有差异，
04:32 需要请求上下文和外部宽度，04:35/36 仅定位旧业务体偏移。包层可剥离返回码，不能直接照搬业务方法偏移。
详见 [MSDK_V4.md](../tools/research/MSDK_V4.md)。这些证据没有提升请求/响应支持等级，没有扩大发送允许列表。

早期 HG724 型号研究只恢复了身份关联；随后代码备份恢复已确认本批灵敏度写入与参数加载链。历史见 [HG724 研究说明](../tools/research/HG724.md)，当前实现以下方0.7.3与 APP_COMMANDS.md 为准，仍无实机证据。

`app-code-path` 表示已从当前 App 内代码备份静态还原特定型号调用链，不代表 SDK 已封装或设备验证。后续恢复结果见 [代码备份恢复](../tools/research/CODE_RESTORATION.md)。整体完整性条件仍未通过。


## 0.7.3 当前 App 参数事务

当前实现见 [APP_COMMANDS.md](APP_COMMANDS.md)。显式 `ronin-2.2.2` 配置提供参数读取与跟随灵敏度读写，四端共享各自已有连接与队列。它与旧研究配置互斥，不新增高级组合功能。ACK=0 仅代表协议响应成功，不能代表物理到位。

静态审计已固定 55 类、631 个方法指纹（含 Ccode）；其中原命令扫描为 54 类、620 个方法。审计输出不含完整厂商代码。通用方法存在不代表该命令有 HG724 调用分支；48 项清单与两个完整性门槛仍不变。


0.7.4 的两个继承源码位字段组已封装为设备事务，见 [APP_SETTINGS.md](APP_SETTINGS.md)。设置共用04:10读取与04:0F写入，并非新增八个独立命令；继承链不能替代本机验收。


0.7.5沿HG702覆盖路径封装04:6A无ACK请求及04:6E查询/通知，见 [APP_CALIBRATION.md](APP_CALIBRATION.md)。没有把Ronin2父类路径直接用于HG724，也不由本机写入或一条Complete报告判定物理完成。


0.7.6完成十二个继承源码命名电机字段的31/32封装，详见 [APP_MOTOR_TUNING.md](APP_MOTOR_TUNING.md)。输入范围、命令空间和ACK已核对，仍无本机接受/效果/持久化证据，两个完整性门槛保持false。


## 平衡测试静态调用链补充

HG724继承的启动路径为普通用户参数04:0F，balance_test/index37/size1，启动值64；不是直接调用04:40。资源存在两条同名参数范围0..1和0..255，加载器按顺序名称覆盖，不能取第一条或假定名称唯一。状态/三轴结果位已定位，零结果字段不能当作通过。详见 [BALANCE_TEST.md](../tools/research/BALANCE_TEST.md)。本批是静态证据与复现工具，未新增SDK接口、发送或硬件证据；运行时仍0.7.6/0.3.6，两个完成门槛仍false。

0.7.7已封装平衡测试固定启动请求与状态/三轴结果，见 [APP_BALANCE_TEST.md](APP_BALANCE_TEST.md)。本机接受/物理完成/中止仍未验收，全协议及高级门槛保持false。

0.7.8提供独立system_calc自动校准请求/状态，来源和未验收项见 [APP_SYSTEM_CALIBRATION.md](APP_SYSTEM_CALIBRATION.md)，没有把它直接计为水平校准完成或实机支持。


多段恢复已扩大到6段49,542条code_item并定位40个模式键UI引用方法；不代表字段或命令覆盖完成，六组模式仍待核对/封装。见 [CODE_BANKS.md](../tools/research/CODE_BANKS.md)。

0.7.9六组按轴档位已跨SDK/UI核对并封装，见 [APP_FOLLOW_MODES.md](APP_FOLLOW_MODES.md)；PF/PTF预设、custom数值、低两位、型号/UI和实机效果仍未完成。

数值静态研究已区分普通18字段和独立配置输入源同包路径；源码证据不等于SDK或型号验收。见 [NUMERIC_PARAMS.md](../tools/research/NUMERIC_PARAMS.md)。

0.7.10封装18项普通数值并以源码证据逐项检查三端目录，见 [APP_NUMERIC_TUNING.md](APP_NUMERIC_TUNING.md)。活动预设和本机效果未验收，不计作全部命令完成。


0.7.11增加独立配置的六项命名数值与显式输入源2同包事务，04:0F写/04:10按外部宽度读；读取不切源，未知源和值保留。源码条件关联至Model.HG724，尚无设备验证。见 [APP_STANDALONE_TUNING.md](APP_STANDALONE_TUNING.md)。这不完成PF/PTF/FPV预设、固件原生程序或全部命令，完整性和高级新增门槛仍false。


2026-10-17预设研究新增26个方法指纹：UserProfile/table_choice、MovementSettingsProfile和GimbalWorkMode分别核对；HG724条件新模式列表为FPV/Custom/3D Roll 360，不能照搬旧PF/PTF位置。业务getPresetID偏移2尚未证明原始BLE偏移，SDK不解码为活动预设。见 [PROFILES.md](../tools/research/PROFILES.md)。运行时仍0.7.11/0.3.11，未新增接口或操作硬件，全命令门槛false。


后续订阅审计确认04:12为CENTER/id7无ACK、最高频道号+位图及本地引用计数刷新；本地停发不能当远端取消。未加密请求型04:24的源payload偏移2已追通，但不代表本机活动预设或04:10参数订阅。见 [SUBSCRIPTIONS.md](../tools/research/SUBSCRIPTIONS.md)。本批不新增SDK发送/解码接口，运行时与全命令门槛不变。


0.7.12将04:24的17个已审计getter接入四端被动缓存，完整已知布局至少74字节，保留未知原值、限定未加密请求型和端点，不触发订阅、主动查询或预设激活。通用源布局不是本机验证，更多字段和全部协议仍未完成。见 [APP_USER_PARAMETERS.md](APP_USER_PARAMETERS.md)。


后续微调/手柄/重置审计固定42方法：微调轴值0/2/4，手柄8字节与FF默认/只重置6项，HG724平台重置010001。保存空体类在两段未见直接调用者，不代表全App否定。详见 [FINE_HANDLE_RESET.md](../tools/research/FINE_HANDLE_RESET.md)。本批未新增SDK发送或实机证据，运行时不变，全命令门槛false。


0.7.13在显式App来源下增加04:36手柄只读查询和8字段原值/bit0解析，不写35/11/13或填04:24缓存；继承路径有源码证据，实际型号布局/效果未验证。见 [APP_HANDLE_SETTINGS.md](APP_HANDLE_SETTINGS.md)。全命令及高级门槛仍false。


0.7.14的sendFineTuneRequest是设备04:07源请求封装，Pitch/Roll的float32参数编码、ACK与主机取消分别处理；不计作高级组合或实际角度完成。暂停稳定/本机效果及其余命令仍未验收。见 [APP_FINE_TUNE.md](APP_FINE_TUNE.md)。


## 0.7.15手柄单字段请求 / 原生0.3.15 build18

四端设备SDK的sendHandleSettingRequest（Python snake别名）显式App来源下仅接受dualChannelMode/tiltDirection/panDirection单字段及整数0/1，8字节35体未指定字节为源默认FF。新对象/独立体，不全量读改写、不新增相机字段。参数停止前验证/快照，复用连接/队列/操作所有权至关联ACK；取消/超时无重放或回滚，NACK直接失败、不缓存兜底成功、不自动回读。结果unspecifiedByteSemanticsVerified/readbackVerified/persistenceVerified及既有设备/物理标志均false。FF实际含义、模式/方向效果、持久化待本机验收。见docs/APP_HANDLE_WRITE.md；没有高级新增或硬件操作，全部命令门槛仍false。


## 0.7.16恢复设置请求 / 原生0.3.16 build19

四端sendFactorySettingsResetRequest（Python snake别名）需显式App来源和sourcePlatform HG724，固定04:13/010001；不是类型枚举103或其他平台空体。停止前验证/快照，复用连接/队列/操作槽至关联ACK。取消/超时/断线不重发、不自动保存/回读/回滚，重连不重放。ACK不证明恢复范围、持久化、重启或物理完成，相关标志false，不自动清零/改写反馈或参数。恢复范围也未证明仅非相机字段。68方法审计新增成功/失败回调，未解析完成。见docs/APP_FACTORY_RESET.md。没有硬件/liveUI/厂商执行或高级新增；全部命令仍未完成。

保存命令六段引用扫描与限制见 [SAVE_CALLERS.md](../tools/research/SAVE_CALLERS.md)，不是本机不支持证明。

新模式40方法审计确认参数17/18/19及34/枚举移位，index2绕过普通三轴开关setter；源回调不串联写入，尚无完整模式SDK或本机效果。见[PROFILES.md](../tools/research/PROFILES.md)。


## 0.7.17轴模式34读写 / 原生0.3.17 build20

四端getAxisMode/sendAxisModeRequest（Python snake别名）在显式App来源下封装34/size1。四个源枚举写0/8/16/24，读(raw>>3)&3，保留raw/unknownBits=raw&0xe7及headerByte，modelLayout/activePreset/device/physical标志false。HG724 UI只定位ThreeAxis及ThreeDRoll360，不宣称全部四种固件支持。源setter整字节写，不擅自RMW或保留其他位，otherBitsPreservationVerified/persistenceVerified=false。参数快照、写先停主机运动并独占至ACK，取消/超时/断线无重放/回滚，NACK不缓存兜底；不自动写132、17/18/19、35或激活预设，不是完整跟随模式。Node/Python有限读并发与原生读占槽差异保留。见docs/APP_AXIS_MODE.md；未操作硬件/执行厂商代码/新增高级任务，全命令未完成。


## 0.7.18普通跟随轴开关 / 原生0.3.18 build21

四端getSmoothTrackAxes/sendSmoothTrackAxesRequest（Python snake别名）显式App来源下封装17/18/19、size1，默认读三轴/可过滤单轴，写非空命名布尔子集，一条0F按yaw/pitch/roll排序，未指定字段省略。源App直接参数数组路径已确认，本次未定位逐轴SDK setter；不将其不存在或本机支持当结论。读raw0/1→enabled false/true，其他→null，保留raw/header、sourceEnabled=(raw==1)与withinSourceRange，不按bit0或错误码丢值。参数快照/写先停/独占至ACK，取消/超时/断线无重放/回滚，重连不恢复请求；不自动写132/34/35/预设/输入源/保存，不是完整模式。atomicApplication/activePreset/modelLayout/device/physical/persistence相关标志false。见docs/APP_SMOOTH_TRACK.md；没有高级新增、硬件/厂商执行，全命令仍未完成。


## 0.7.19配置0与工作模式62 / 原生0.3.19 build22

四端getUserProfile/sendUserProfileRequest、getWorkMode/sendWorkModeRequest（Python snake别名）显式App来源下独立读写0/62、size1。配置源范围0..5，源UI名仅0/1/2=M1/M2/M3，其他不推断运动预设；工作写仅精确Free/Flower/Fpv/Center四枚举，读取未知128/255保留raw并sourceMode=null、范围标志分别true/false。索引0不是空请求。与MovementSettingsProfile、推送preset、34/17-19/132等域分开，不自动组合模式或激活其他配置。写前验证/快照/停主机运动、独占至ACK，取消/超时/断线不重放/回滚/保存/读回，重连不重放，NACK不缓存兜底。modelLayout/activePreset/device/physical/persistence相关标志false，见docs/APP_PROFILE_VALUES.md。41方法源审计补充原始整数/枚举匹配与value访问器，未操作硬件、执行厂商代码或新增高级功能，全命令仍未完成。

[六段命令引用矩阵](../tools/research/COMMAND_REFERENCES.md)覆盖40枚举/39命令值，记录0D未知和0A别名/实现候选差别；不是全部固件协议或型号支持清单。


最新[原生角度控制研究](../tools/research/ANGLES.md)已区分04:0A两种布局与HG724继承rotate的04:14路径；能力/地址/暂停及物理完成仍待核对，未新增当前App角度发送接口。


后续[角度能力与包上下文研究](../tools/research/ANGLE_CONTEXT.md)核对初始化覆盖、接收ID传递及EYE两个不同重载；本机地址、依赖适用性/恢复与物理完成仍未验收，没有新增发送。


[暂停状态与等待依赖审计](../tools/research/STABILIZATION_DEPENDENCY.md)区分源stabilization状态、3秒等待与真实云台停止/到位；关闭也返回paused、等待不按请求序号关联，未新增运行时功能或声明本机支持。


[回中平台分支与App入口研究](../tools/research/RESET_ROUTES.md)已区分通用SpecialControl流程和三处直接FE01源分支；现有实测回中保持不变，未开放其他模式或混合控制发送。


0.7.20新增[手柄状态被动候选](APP_HANDHELD_STICK.md)，仅显式App来源、无58发送/订阅，真实57布局、单位与轴映射等待本机验收；未新增高级功能。


0.7.21新增[异常与电量被动候选](APP_SOURCE_STATUS.md)，显式App来源、原始位/255保留，不触发请求或自动控制；本机布局与通知仍未验收。


[教程命令源审计](../tools/research/TUTORIAL.md)记录未知步骤回退与32位移位边界；未定位HG724业务入口，不新增教程发送或以教程标志判定运动完成。


[HG724支持键规则研究](../tools/research/KEY_SUPPORT.md)区分声明支持谓词、缓存动作注册与原生BLE命令；保留多匹配歧义，不据键数量声明协议完整或新增发送。


[HG724初始化与动作声明分派](../tools/research/REGISTRATION.md)补齐继承目录及两个动作的静态声明链，仍非运行时注册或本机验收；不改变SDK发送与高级门槛。


[固件动作程序通用源审计](../tools/research/PROGRAMS.md)核对62/25/37/63请求与38/64/6B状态差异；仅静态业务体证据，尚无HG724完整路径或SDK新增发送，全命令门槛false。


[程序菜单与HG724条件分类](../tools/research/PROGRAM_ENTRY.md)补齐产品缓存/布局声明链，区分快门线帮助与检查函数可达性；尚未证明完整型号工作流，不新增发送或高级功能。


[主页面挂载与轨迹UI工作流](../tools/research/TRACK_WORKFLOW.md)补齐静态挂载链，区分ACK后的界面状态、重订阅和物理停止；仍未开放程序SDK或高级功能。


[程序基础接收路径](../tools/research/PROGRAM_RECEIVE.md)区分ACK返回码与业务首字节、6B双路分派及扩展命令表边界；仅静态研究，不新增SDK发送或高级功能。


0.7.22新增[程序状态被动候选](APP_PROGRAM_STATUS.md)：显式App来源下38/64/6B独立帧快照，未知/重复记录保留，无查询/订阅/自动ACK，不等于物理完成；完整命令仍未验收。


0.7.23新增[单次程序状态请求](APP_PROGRAM_REQUEST.md)：显式App来源、固定type2与三个命名程序，仅关联ACK、业务体不透明；不承诺新通知，不增加连续订阅或动作执行，本机未验收。


0.7.24新增[程序状态推送启停请求](APP_PROGRAM_SUBSCRIPTION.md)：显式program与布尔enabled，固定type0/1及关联ACK；不证明远端订阅状态、不自动维护或恢复订阅，不发送动作程序命令。本机仍未验收。


新增[轨迹路点与ActualPose审计](../tools/research/TRACK_POINTS.md)：UI秒数分段、首点/Roll规则及04:66缓存来源已核对，不能把原生轨迹角度直接当作现有机械关节角。仅研究，无SDK发送或硬件操作，运行时仍0.7.24/0.3.24，全命令门槛false。


0.7.25新增[外设状态源候选](APP_PERIPHERAL_STATUS.md)：46源类型/43 getter视图、保留tag21碰撞和GPS整数截断；不改现有姿态/关节，不自动ACK/订阅或控制，本机未验收。


新增[完整订阅键与初始化条件审计](../tools/research/SUBSCRIPTION_CATALOG.md)：152个注册键分开记录显式索引、21个元数据条件键与2个型号条件；不将缺失0或资源预期索引自动变成SDK发送表。仅离线研究，运行时仍0.7.25/0.3.25，全命令门槛false。


## 订阅初始化审计（2026-10-18）

固定六段13方法审计确认元数据异步加载、逐项发布与BaseCommand构造时一次性捕获；不能推断真实调度、竞争或捕获0。独立SDK可明确选择固定DB已加载的索引分支，无需依赖App缓存；本机路由/通知/远端取消仍未验证。见[SUBSCRIPTION_INIT.md](../tools/research/SUBSCRIPTION_INIT.md)和证据protocol/research/ronin-subscription-init-evidence.json。两次实际提取JSON逐字节一致，新增7项研究测试。此研究检查点不发布新的运行时版本；已提交运行时仍0.7.25/0.3.25。单次订阅SDK正在工作树中开发，尚未交付，不计作已完成；全命令与高级门槛仍false，无硬件或厂商执行。


## 0.7.26单次命名参数订阅 / 原生0.3.26 build29

显式App来源下发送固定DB已加载/HG724静态分支的152命名键非空单次04:12请求，CENTER/id7、无ACK；报告21元数据和2型号条件键。不提供空集停止、后台刷新、反向请求或重连重放；三条中位前导及独占操作槽，不由发送成功判断远端订阅、通知新鲜度或物理效果。详见[单次参数订阅](APP_PARAMETER_SUBSCRIPTION.md)。此版本扩展此前“仅研究/工作树开发”的历史状态；实际型号/路由/通知/远端停止仍待验收，全命令及高级门槛false，无硬件/实时UI/厂商执行。


## 外设数据04:69源审计（运行时不变）

固定六段36方法、12数据类型/4来源枚举，核对tag2的控制来源及三轴signed16原值、无ACK start、空doPack和基础双路分发。仅定位跟踪界面读取两轴的一个直接调用者，无HG724或物理单位/路由证据。源旧字段保留/短包只清速度与离线独立帧视图区分；未增加SDK收发、相机/视觉或高级功能。见[EXTERNAL_DEVICE.md](../tools/research/EXTERNAL_DEVICE.md)和protocol/research/ronin-external-device-evidence.json。运行时仍0.7.26/0.3.26，全部命令及高级门槛false，无硬件/实时UI/厂商执行。


## 0.7.27外设数据被动候选 / 原生0.3.27 build30

显式App来源下externalDeviceStatus/kind=externalDevice解析04:69完整TLV，tag2保留来源及三轴signed16原值、未知/重复与尾字节；Other7与未知原值分开，不继承源单例旧值或短包清零副作用。来源/断线清空，观察者隔离；不发送/订阅/自动ACK，不完成查询或改变姿态/关节、运动所有权。见[外设数据候选SDK](APP_EXTERNAL_DEVICE_STATUS.md)。本机布局/单位/参考系均未验收，未新增相机/视觉/高级功能，无硬件/liveUI/厂商执行，全命令门槛false；此前“仅研究未接SDK”为历史状态。


## 校准08/30域与近似类绑定研究

固定六段48方法、17直接调用、9类型化声明/9枚举引用，确认04:30实际绑定SensorCalibrateStatus而非近似AutoCalibrationStatus；30状态COMPLETE0/PROCESSING1/FAIL3/OTHER9，与08响应FAIL0/SUCCESS1/PROCESSING2分开，不复用bool inProgress或system_calc表。08单字节部件及ACK业务偏移已核对，型号入口/实际扩展、路由/物理中止仍未完成。详见[校准源审计](../tools/research/SENSOR_CALIBRATION.md)及protocol/research/ronin-sensor-calibration-evidence.json。仅离线研究，运行时0.7.27/0.3.27不变，没有SDK收发、相机/视觉/高级新增或硬件/liveUI/厂商执行，完整命令门槛false。


## 0.7.28传感器校准被动候选 / 原生0.3.28 build31

显式App来源下sensorCalibrationStatus/kind=sensorCalibration解析04:30两字节源进度/状态及尾部，保留0..255原值，映射0/1/3/9并标记未知；不复用08状态或旧inProgress，不补短包默认，不由COMPLETE结束查询/运动。缓存复制/不可变、观察者隔离、来源/断线清空。见[传感器校准候选SDK](APP_SENSOR_CALIBRATION_STATUS.md)。没有查询/订阅/自动ACK/校准触发或相机/视觉/高级新增；本机/单位/请求关联与物理完成未验收，无硬件/liveUI/厂商执行，全命令门槛false。此前当前App30“未接SDK”限定为历史状态。


## 校准入口条件与HG724静态分支研究

63方法/2布局核对SystemStatus→新设置构造链、普通GYRO05/高级AUTO00的04:08及MotorEnabled缓存门槛。所选项与ModelName均HG724的显式源码情形中，普通隐藏/高级显示且旁路版本；阈值00.02.32.25严格大于、缓存/异步可见性与实际设备分开。高级ACK后60秒本地计时和百分比显示不证明固件中止/请求关联。见[校准入口研究](../tools/research/CALIBRATION_ENTRY.md)及protocol/research/ronin-calibration-entry-evidence.json。不与system_calc/index36混用，未新增SDK收发/高级功能或硬件/liveUI/厂商执行，运行时仍0.7.28/0.3.28，完整命令门槛false。


## 校准默认包头与条件加密研究

固定六段28方法审计确认04:08新对象默认APP/id0→GIMBAL/id0、条件加密前flags40；NEEDACK.YES线上值2不是ordinal。通用发送层可按可变会话策略加密包括命令集/命令号的区间；接收事件关闭仍可能运行分类分支，不把业务Encrypt.NO当最终线上保证。见[校准传输审计](../tools/research/CALIBRATION_TRANSPORT.md)（仓库根目录）及protocol/research/ronin-calibration-transport-evidence.json。未实现/执行JNI或APK、未新增SDK收发/高级功能、没有硬件或实时UI，运行时仍0.7.29/0.3.29，完整命令门槛false。


## BLE直连路由与默认策略研究

固定六段37方法核对BluetoothService→Main DJIPackManager→通用parseOne，以及监听、常规发送队列、服务切换、分片与GATT写入。Main继承needCheckEncrypt=true且构造enabledSetDataEvent=true，与DataBase共享加密管理器单例；源路由/构造策略已定位，实际会话与对端接受仍未验证。五处直接字段写入限构造，其他管理器false不套用到BLE。见[BLE路由研究](../tools/research/BLE_ROUTE.md)（仓库根目录）及protocol/research/ronin-ble-route-evidence.json。未新增SDK收发/解密/高级功能，无硬件/liveUI/厂商执行，运行时0.7.29/0.3.29及完整命令false不变。


## 04:08 ACK与业务域研究

固定bank05独立核对20方法，基础表ACK剥离ccode后part/status对应原始payload1/2；GIMBAL回调成功仅返回码0，与业务SUCCESS1分开。短业务体不补PROCESSING；源混合命令key仅命令集/命令/序号，不照搬到SDK严格会话/ACK/端点关联。见[校准ACK研究](../tools/research/CALIBRATION_ACK.md)（仓库根目录）及protocol/research/ronin-calibration-ack-evidence.json。没有SDK发送/解密/高级新增、硬件/liveUI或厂商执行，运行时0.7.29/0.3.29及完整命令false不变。


## HG724手柄工厂与04:58键绑定研究

固定bank05核对19方法与注解，HG724条件工厂选择MobileHandheldControllerAbstraction；StickGimbalControlEnabled键支持和实际Setter注解对应04:58布尔类。方法名中的MicroPhones不定义功能，不新增麦克风/相机接口。工厂参数1是数量、普通index0，不改作接收地址；源链不证明现场反射/注册或固件效果。见[手柄绑定研究](../tools/research/HANDHELD_BINDING.md)（仓库根目录）及protocol/research/ronin-handheld-binding-evidence.json。未新增SDK收发/高级功能，无硬件/liveUI/厂商执行，运行时0.7.30/0.3.30及全命令false不变。
