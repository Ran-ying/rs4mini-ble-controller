# 设备 SDK 命令审计与高级开发前置条件

2026-10-16，0.7.1 / 原生 0.3.1。**尚不能确认 RS 4 Mini 全部非相机 BLE 命令都已枚举、解析并封装。**
机器清单是 [protocol/COMMANDS.json](../protocol/COMMANDS.json)，目前记录 19 个命令或缺口条目；
它不是厂商完整命令表，不能以“所有已知代码已封装”代替“所有设备命令已知”。

用户指定的顺序：两层拆分 → 底层全部范围内命令解析/封装验收 → 继续新增高级功能。
第一步已实施；第二步未完成，因此第三步暂停。现有高级功能保留并回归。

## 审计结果

`implemented` 表示已有请求编码/受控发送实现，不代表型号兼容或物理效果确认。
`partial` 表示仅部分字段/操作已明确；`raw` 表示只提供原始消息，不等于业务字段已解析。
`hardware` 仅表示存在本机历史观测，具体覆盖看最后一列和 `VALIDATION.md`；
`other-model` 和 `none` 不得提升为本机支持。通知没有请求，记为 `not-applicable`。

| 命令/缺口 | 内容 | 请求封装 / 响应解析 | 设备证据 | 尚缺什么 |
|---|---|---|---|---|
| `00:01` | 版本查询 | `implemented` / `raw` | `other-model` | 响应返回原始消息，型号/版本字段未确认 |
| `04:01` | 虚拟摇杆及中位停止 | `implemented` / `not-applicable` | `hardware` | 历史设备行为已验证，无固件执行确认 |
| `04:02` | 位置查询 | `implemented` / `raw` | `other-model` | 本机历史尝试未收到有效响应，不能判断不支持 |
| `04:05` | 姿态与关节通知 | `not-applicable` / `partial` | `hardware` | 姿态/关节映射已确认；四元数顺序及部分标志未知 |
| `04:08` | 校准触发候选 | `not-exposed` / `unknown` | `other-model` | 其他型号研究有自主运动和中止风险，不提供触发 |
| `04:0B` | 控制状态查询 | `implemented` / `raw` | `other-model` | 响应字段未确认 |
| `04:0C` | 原生速率候选 | `implemented` / `unknown` | `other-model` | 轴序/单位/释放仅有 RS 3 来源，本机未验证 |
| `04:0F` | 休眠/唤醒候选 | `implemented` / `partial` | `other-model` | RS 3 与 Mini 字节不同，本机效果未知 |
| `04:14` | 原生绝对角候选 | `implemented` / `unknown` | `other-model` | 末参数单位、参考系与本机兼容性未知 |
| `04:1C` | 设备类型查询 | `implemented` / `raw` | `other-model` | 响应枚举未确认 |
| `04:1E` | degree-info 请求 | `implemented` / `raw` | `hardware` | requestDegreeInfo 封装关联原始响应；本机历史 00 不等于完整字段解析或增频确认 |
| `04:30` | 校准进度候选通知 | `not-applicable` / `partial` | `other-model` | 仅被动解析，不触发校准 |
| `04:4C` | 重置/模式命令中的三轴回中 | `partial` / `unknown` | `hardware` | 只确认 FE01/flags40 三轴回中；其余位/模式/单轴语义未知 |
| `04:66` | 状态 TLV 候选通知 | `not-applicable` / `partial` | `other-model` | 保留 TLV 原始量，不假设本机 tag 语义 |
| `0D:02` | 电量候选通知 | `not-applicable` / `partial` | `other-model` | 百分比仅为其他 Mini 研究格式，本机未证实 |
| `unknown:follow-mode` | 跟随模式与手柄参数 | `unknown` / `unknown` | `none` | 缺少本机型号分支、命令与枚举证据 |
| `unknown:motor-calibration` | 电机参数/自动整定/水平校准 | `unknown` / `unknown` | `none` | 不能由已有运动输入组合替代 |
| `unknown:firmware-program` | 固件动作程序 | `unknown` / `unknown` | `none` | 缺少上传/启动/状态/取消的完整证据 |
| `unknown:device-management` | 激活/绑定/恢复设置/固件管理的 BLE 覆盖 | `unknown` / `unknown` | `none` | 是否通过本 BLE 链路提供及其协议尚未枚举；连接成功不证明设备管理命令已全覆盖 |

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
