# 当前研究方法与推进路线

更新：2026-10-20。此页是后续研究的集中入口；专题文档保留各自提交时的历史范围。当前运行时 Node/Python/Web 0.7.33、macOS 0.3.33。**八段直接引用重审（表中优先级 1–5）已完成**；这不等于全部离线语义已关闭。仍开放的静态项见下方「剩余离线队列」；inventoryComplete 仍 false。实机验收（原优先级 6）仍在用户回家之后，且不因缺少 HG724 具名调用者就断定无继承业务入口。版本和提交以 [项目状态](PROJECT_STATUS.md) 与 Git 历史为准。

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

以下是计划。表中优先级 1–5 仅表示 **PREFIX_BANKS 八段直接引用 / 定义面重审** 已落档；**不是**「全部静态语义已关闭」。缺少 HG724 具名调用者只说明该名字路径未命中，**不能**写成「无继承业务入口」或「设备不支持」。每项结果回填命令清单及对应专题；若发现更强的新线索，可调整顺序并记录原因。

| 优先级 | 任务与现有入口 | 本阶段范围（已完成） | 保留边界 |
|---|---|---|---|
| 1 ✓ 八段重审 | 04:11 保存：[SAVE_PREFIX](../tools/research/SAVE_PREFIX.md) | PREFIX_BANKS 调用/分配/字段/枚举注册分类；01/07 无命中；无外部直接调用 | 仍无已证实的 HG724 持久化链；不开放 saveSettings；参数写入 ≠ 持久化 |
| 2 ✓ 八段重审 | 04:0D/2C/0A：[GAP_PREFIX](../tools/research/GAP_PREFIX.md) | 定义/外部调用/枚举外引用重审；01/07 无增量 | 0D 无实现类、2C 无外部调用、0A 仍仅 DT501；均不开放发送 |
| 3 ✓ 八段重审 | 04:14/0C/4C：[MOTION_PREFIX](../tools/research/MOTION_PREFIX.md) | 0C 布局与 UI 调用、14/4C 八段调用面 | **不**关闭：动态能力/索引地址/EYE、完成与中止、参考系、按轴回中；不开放 14/0C；不替换 04:01 |
| 4 ✓ 八段重审 | 04:25/37/62/63：[PROGRAM_PREFIX](../tools/research/PROGRAM_PREFIX.md) | 类外调用面；无 HG724 **具名**入口 | **不**关闭：程序型号路径、相机/曝光/录制隔离；纯稳定器原语与程序执行仍关闭 |
| 5 ✓ 八段重审 | 全清单：[INVENTORY_PREFIX](../tools/research/INVENTORY_PREFIX.md) | bank05 现场提取 CmdIdGimbal 与 COMMANDS 比对；40 非排除均已登记 | inventoryComplete 保持 false；bank01 激活控制器仍缺口；不开放激活写入 |
| HW | 实机验收：[HARDWARE_CHECKLIST](HARDWARE_CHECKLIST.md) | （待用户回家） | 研究期间不扫描/连接/移动设备，不执行厂商 APK/Java/JNI/native 或实时 UI |

### 剩余离线队列（静态语义，仍开放）

在实机验收之前，优先用固定 PREFIX 输入与自写工具推进下列项。每项单独成专题/提交；结论必须区分「静态已证实」与「需硬件确认」。

| 序号 | 主题 | 具体未决 | 入口线索 |
|---|---|---|---|
| A ✓ 静态耗尽 | 动态能力 / 索引地址 / EYE | 端到端链 + 四子项静态耗尽：App rotate 无条件发 EYE；index 默认0/映射；EYE/GIMBAL `isNeedEncrypt=true`；Ronin2 参数能力路径存在。**本机/直连验证未做** | [QUEUE_A_SEMANTICS](../tools/research/QUEUE_A_SEMANTICS.md)、[ROTATE_EYE_TRANSPORT](../tools/research/ROTATE_EYE_TRANSPORT.md) |
| B | 参考系 | 姿态/关节/电机角与业务「参考系」字段的静态绑定；不能把现有 04:05 关节直接当作固件轨迹角 | [TRACK_POINTS](../tools/research/TRACK_POINTS.md)、运动专题 |
| C | 完成 / 中止 | 动作完成通知、abort/cancel 路径、与会话/ACK 的关联；静态只记源码契约 | 程序状态 / 运动控制类 |
| D | 程序型号与相机隔离 | 全景曝光、轨迹录制字段与纯云台原语的边界；型号/组件条件 | [PROGRAM_PREFIX](../tools/research/PROGRAM_PREFIX.md) |
| E | 会话版本 / 状态关联 | 查询版本、激活/CENTER 状态缓存与会话关联；不能把版本查询混入激活缓存 | [ACTIVATION](../tools/research/ACTIVATION.md)、[ACTIVATION_RECEIVE](../tools/research/ACTIVATION_RECEIVE.md) |

完成底层全命令门槛之后，才重新规划高级组合；不能把八段直接引用重审完成或包构建成功当作该门槛通过。

## 复现与接手

从实际仓库根目录开始，依次读 `AGENTS.md` → [当前状态](PROJECT_STATUS.md) → 本页 → [命令清单](../protocol/COMMANDS.json) → 所选专题。各专题保存固定输入、方法指纹、工具命令、测试及未决问题；[工具目录](../tools/research/README.md) 提供复现入口。

- 八段恢复的完整命令和可选 Androguard 环境见 [PREFIX_RESTORATION.md](../tools/research/PREFIX_RESTORATION.md)。本机既有八段目录为 `work/research/prefix-restored-final-b/`，文件名 `business-XX-prefix-code-restored.dex`；先核对 PREFIX_BANKS 固定哈希，不只按文件名选输入。
- 统一检查：`sh tools/check-offline.sh`。专题工具的真实输入提取与纯测试都要运行，不能只用测试向量代替 APK 复现。工具参数遵循该专题文档及 `--help`，不将旧六段脚本直接改名当八段结果。
- APK、派生 DEX/库、完整反汇编及可选依赖留在忽略的 `work/`，不随 Git 分发；Git 保存自写工具、事实/指纹 JSON、合成向量、测试和文档。`work/` 探索稿不是交付证据，结论必须提升为仓库中可复核的专题记录。
- 每轮结束更新本页优先级、专题剩余问题、命令清单及项目状态。提交/CI 信息以 Git 和实际运行结果为准；不要求后续接手者依赖聊天记录。
