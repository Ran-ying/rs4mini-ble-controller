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
