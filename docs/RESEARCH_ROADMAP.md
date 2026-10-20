# 当前研究方法与推进路线

更新：2026-10-20。此页是后续研究的集中入口；专题文档保留各自提交时的历史范围。当前运行时 Node/Python/Web 0.7.33、macOS 0.3.33。优先级1（04:11 八段保存重审）已完成且仍不开放 saveSettings；下一项为 0D/2C/0A。版本和提交以 [项目状态](PROJECT_STATUS.md) 与 Git 历史为准。

[命令清单](../protocol/COMMANDS.json) 当前有49项已知命令或缺口，**不是49项已完成设备能力**；`inventoryComplete=false`、`advancedDevelopment.allowed=false`。设备 SDK 与主机组合遵循 [架构](ARCHITECTURE.md)，`moveTo()` 不计作固件命令。底层验收完成前不增加高级组合。

## 研究方法：从固定输入到设备证据

1. **固定输入与恢复范围。** 固定 Ronin 2.2.2/7096 APK 的 SHA256 为 `4ef0aa1e351990168a522500728790e22794618b0bcbd4c6277c7375148dc4f4`。先验证输入与派生视图哈希，再解析。当前八段具名视图及52,679条 code_item 备份见 [恢复方法](../tools/research/PREFIX_RESTORATION.md)。源 Adler32 一致、源 SHA1 不匹配分别保留；派生校验和不充当原始未保护 App 身份证明。新审计使用 `ronin_prefix_restore.PREFIX_BANKS`，旧六段 `BANKS` 保留历史复现用途。
2. **定义与调用分开。** 分别记录 wire 值、枚举 ordinal、构造参数、显式 null 与未知类型。按实际指令的 owner/name/prototype 追直接调用；字符串、字段类型、分配、class 常量不充当调用。报告扫描段、带代码方法与匹配规则；“未找到直接调用”不能写成“不支持”，八段可读也不等于所有 native/反射/动态路径已恢复。
3. **追到 HG724 业务路径。** 逐层核对继承、override、工厂、注解注册、资源加载顺序、型号/组件/版本条件和可变缓存。展示名称、静态 HG724 分支、UI 可见性、默认能力分别记录，不能替代现场身份、实际调用或固件支持。记录所选入口与其他入口的差异，避免只看同名类。
4. **把包层接上业务层。** 对每个方向核对命令集、端点/id、flags、ACK/推送、ccode 剥离、加密策略、混合分发与会话关联。业务 offset 不能直接照搬为原始 BLE offset；`Encrypt.NO` 不证明最终传输不加密。参考 [BLE 路由](../tools/research/BLE_ROUTE.md) 与 [校准 ACK](../tools/research/CALIBRATION_ACK.md)。
5. **先形成纯离线语义。** 自写工具复现长度、字节序、signed/unsigned、窄化、float32 顺序、未知值、尾部和源异常行为。源缓存回退、短包补零等行为要如实研究，但 SDK 不因此伪造新响应。参考 [CENTER 接口](APP_CENTER_INFO.md) 如何将源 SN 缓存行为与本次响应契约分开。
6. **证据足够后封装设备 SDK。** 每项单列请求、响应、型号来源、ACK 关联、取消/超时/断线与物理完成；有静态源链的候选可按既有显式 App 配置封装，同时保留 `deviceVerified=false`。缺少可界定载荷/路由的命令继续关闭发送。Node 主实现，同步 Python/Web/macOS 的适用接口，应用仍通过高级门面进入，不增加未经授权的高级组合。
7. **分层验证并交付。** 固定输入独立提取两次逐字节比对，保存方法指纹和事实 JSON；用自写共享向量测 codec，用 fake transport 测关联和生命周期，再运行统一离线检查。运行时变更才更新版本、构建并实际隔离安装核验包；提交/推送后核对 CI 的完整 head SHA。离线通过不升级为硬件验证。

证据按“定义/布局 → 型号静态路径 → SDK 离线实现 → 目标实机”分别登记，不以一个总的“已支持”合并。若缺证据，记录具体未决问题及能排除什么，继续其他可独立研究项，不用猜测补允许列表。

## 下一步顺序与完成条件

以下是计划，尚未完成的八段重审不能因写入本页而视作已执行。每项结果回填命令清单及对应专题；若发现更强的新线索，可调整顺序并记录原因。

| 优先级 | 任务与现有入口 | 下一步具体问题 | 本阶段完成条件及保留边界 |
|---|---|---|---|
| 1 ✓ | 04:11 保存：[八段重审](../tools/research/SAVE_PREFIX.md)（历史[六段](../tools/research/SAVE_CALLERS.md)） | 已用 PREFIX_BANKS 重做调用/分配/字段/枚举注册分类；01/07无命中，无外部直接调用 | 2026-10-20 完成：新工具+证据+测试；仍无 HG724 链，不开放 saveSettings；不把参数写入等同持久化 |
| 2 | 04:0D、04:2C、04:0A：[教程](../tools/research/TUTORIAL.md)、[角度](../tools/research/ANGLES.md)及命令清单 | 逐项将旧六段引用结论重审为八段；0D 查实际定义/打包或字面量包，2C 查 HG724 入口/恢复，0A 区分两种10字节布局与 DT501 UVC 调用 | 明确每项定义、外部调用、型号路径、载荷/ACK 的已知与缺失；不把0D等同参数35电机位、不把通用类当本机支持 |
| 3 | 04:14/0C/4C：[角度上下文](../tools/research/ANGLE_CONTEXT.md)、[复位路由](../tools/research/RESET_ROUTES.md) | 补动态能力、实际 index/接收地址、EYE 条件、参考系/单位、完成/中止；工作模式及按轴回中分别追源 | 源请求/响应和条件可以完整说明后再评估 App SDK；保留其他型号实验配置边界，不沿用旧 MSDK 轴枚举或把 ACK 当到位 |
| 4 | 04:25/37/62/63：[程序](../tools/research/PROGRAMS.md)、[入口](../tools/research/PROGRAM_ENTRY.md)、[路点](../tools/research/TRACK_POINTS.md) | 补 HG724 入口、ActualPose 与 MotorAngle/04:05 的关系、首点规则、执行/停止及相机字段隔离 | 先决定哪些纯稳定器原语可独立开放；相机曝光/拍摄与视觉功能不在当前范围；没有可靠停止与相机隔离证据不开放程序执行 |
| 5 | 全清单与设备管理缺口：[SDK 覆盖](SDK_COMMANDS.md)、[CENTER GET](APP_CENTER_INFO.md) | 逐项复核 remaining，继续找遗漏命令/别名；补会话版本、设备身份、状态请求关联等证据 | 清单完整性和每条目标验收独立判断；00:32 GET 不升级为激活/绑定/版本协商，不为了凑全覆盖开放激活写入 |
| 6 | 用户回家后的实机验收：[清单](HARDWARE_CHECKLIST.md) | 在用户确认现场条件后记录设备/固件/载荷，按清单先只读、再逐项受控动作和停止测试 | 记录真实收发、效果及失败恢复；当前研究期间不扫描、连接或移动设备，不执行厂商 APK/Java/JNI/native 代码或实时 UI |

完成底层全命令门槛之后，才重新规划高级组合；不能把静态研究完成或包构建成功当作该门槛通过。

## 复现与接手

从实际仓库根目录开始，依次读 `AGENTS.md` → [当前状态](PROJECT_STATUS.md) → 本页 → [命令清单](../protocol/COMMANDS.json) → 所选专题。各专题保存固定输入、方法指纹、工具命令、测试及未决问题；[工具目录](../tools/research/README.md) 提供复现入口。

- 八段恢复的完整命令和可选 Androguard 环境见 [PREFIX_RESTORATION.md](../tools/research/PREFIX_RESTORATION.md)。本机既有八段目录为 `work/research/prefix-restored-final-b/`，文件名 `business-XX-prefix-code-restored.dex`；先核对 PREFIX_BANKS 固定哈希，不只按文件名选输入。
- 统一检查：`sh tools/check-offline.sh`。专题工具的真实输入提取与纯测试都要运行，不能只用测试向量代替 APK 复现。工具参数遵循该专题文档及 `--help`，不将旧六段脚本直接改名当八段结果。
- APK、派生 DEX/库、完整反汇编及可选依赖留在忽略的 `work/`，不随 Git 分发；Git 保存自写工具、事实/指纹 JSON、合成向量、测试和文档。`work/` 探索稿不是交付证据，结论必须提升为仓库中可复核的专题记录。
- 每轮结束更新本页优先级、专题剩余问题、命令清单及项目状态。提交/CI 信息以 Git 和实际运行结果为准；不要求后续接手者依赖聊天记录。
