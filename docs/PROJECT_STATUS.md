# 项目状态与接手入口

更新日期：2026-10-16。当前源码检查点为 Node/Python/Web **0.7.2**、macOS 原生面板 **0.3.2**。

**本轮四端代码扩展、离线验收和本地打包交付已完成；“全部非相机 BLE 能力”这一整体目标尚未完成。**
用户已要求将源码与相关信息提交至 GitHub。本记录随源码版本保存，提交和远端状态以 Git 历史为准；
这不是 npm 发布或 GitHub 二进制 Release。

## 架构边界（2026-10-16）

用户进一步要求区分蓝牙设备 SDK 和基于 SDK 的运动组合。归属、姿态/关节含义及剩余需求的可行性已固定在 [ARCHITECTURE.md](ARCHITECTURE.md)。
两层运行时模块已拆分；应用仅使用高级 `RS4Mini` / `RSGimbal` 对象，基础方法也通过它访问底层。
用户新增前置条件：全部设备命令解析与封装验收完成前，不再新增高级功能。该条件目前尚未满足，见 [SDK_COMMANDS.md](SDK_COMMANDS.md)。
设备协议能力与软件任务分别验收，不能用上层功能数量衡量新增 BLE 指令数量。

## 已完成的源码范围

- 三轴速度、停止、三轴回中；姿态与机械关节反馈解码；`getAttitude()`、`getJointAngles()`、`moveTo()`。
- 生命周期截止时间、运动互斥与取消、故障清理；显式启用的有界自动重连，重连后不恢复旧运动。
- 速度关键帧轨迹、关节路点与停留、保存位置和按轴返回；显式分量顺序的四元数数学转换。
- Python、Web 和原生面板已按各端方式接入；API、可配置项与查询并发语义存在差异，见根 README 和各端说明。
- 显式 `rs3`/`rs3mini` 研究配置下的限定查询、休眠/唤醒、原生角度/速率及被动状态解析。
  来源是其他型号，尚无本设备兼容性证据；普通 `moveTo()` 继续使用已确认的速度帧加关节反馈。

## 验证证据

| 验证 | 本地结果 |
|---|---|
| Node | 69 项生命周期/运动/扩展测试，另有协议与遥测检查 |
| Web | 12 项模拟 GATT 与页面事件检查 |
| Python | 3.8.10/Bleak 0.22.3 和 3.12.13/Bleak 1.1.1，各 48 项 |
| macOS | 48 项纯核心、57 项假设备和 3 项独立设备 SDK 断言；面板与探针构建及 ad-hoc 签名通过 |
| 类型与安装包 | TypeScript 5.9.3 strict/NodeNext；Node tarball 安装后 69 项、Python wheel 安装后 48 项通过 |

离线复现入口是 `sh tools/check-offline.sh`；安装要求见根 README。
静态研究工具另有 4 项合成边界测试通过。
源码提交 `f15ba51` 的 [GitHub Actions 独立检查](https://github.com/Ran-ying/rs4mini-ble-controller/actions/runs/38867602073) 已成功；后续提交以各自运行结果为准。
详细证据和历史实机读数见 [VALIDATION.md](VALIDATION.md)。

0.5.0 部署后的真实连接采样成功（5 秒、5 帧、约 1 Hz）。历史版本有分轴低速定位记录，
但不为新版本的取消、轨迹、断线恢复或多轴运动背书。用户离家后没有扫描、连接或移动设备；
新 UI 可视检查也未完成。

## 未完成项与下一步

1. 按 [HARDWARE_CHECKLIST.md](HARDWARE_CHECKLIST.md) 进行统一实机和可视验收，登记固件、模式、负载、
   平衡、系统/运行时、目标与到位/停止后的读数。用户返回并要求测试之前，不操作硬件。
2. 补充真正单轴回中、跟随模式、校准/电机调参、固件原生轨迹/全景等协议依据与实现。
   保存位置按轴返回不等于固件单轴回中，软件轨迹不等于固件原生轨迹。
3. 受控验证其他型号实验配置与本机的兼容性；确认四元数顺序、坐标约定和更多状态字段。
   没有证据的部分继续标记未知，不从离线测试或候选类名推断兼容。

约 1 Hz 反馈、经验角速度换算、BLE 停止的物理效果与机械精度均有适用限制，
不能据此宣称全部蓝牙能力或全负载精度已经实现。相机/视觉仍不在范围内。

## 长期维护入口

- [AGENTS.md](../AGENTS.md)：用户决定、协议约束、测试与仓库卫生。
- [CAPABILITIES.md](CAPABILITIES.md)：已实现、实验支持和缺口的功能矩阵。
- [EXPANSION_PLAN.md](EXPANSION_PLAN.md)：当前扩展计划；[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) 为 0.6.0 历史阶段。
- [PROTOCOL.md](PROTOCOL.md)、[RESEARCH_NEXT.md](RESEARCH_NEXT.md)：协议证据和研究线索。
- [Node API](../node/API.md)、[变更记录](../node/CHANGELOG.md)：主实现公共契约与版本变更。

只提交可维护源码、合成测试与匿名结果。设备 ID、原始抓包、凭据、依赖、生成应用、
外部研究仓库和 Ronin APK 不进入 Git。后续验收有新证据时，同步更新本文件、协议/能力表和验证记录。

## 0.7.2 底层研究增量

官方 APK 中 8 段隐藏 DEX 的 6 段已能结构化读取元数据，得到 43 项命令枚举和两份参数表线索。
关键方法仍为保护桩，不能从枚举或参数名直接生成设备写入。命令清单扩充到 48 条，仍不完整。
SDK 仅增加研究配置下的被动参数响应原始结构解析；没有新增发送命令或高级功能。
工具与证据固定在 `tools/research/`、`protocol/research/`，协议与本机验收条件仍未通过。


## 后续底层研究（2026-10-16，运行时版本未变）

官方 MSDK provided 4.18 的只读交叉研究获得旧版回中/模式、参数索引请求及手柄参数业务体候选。
发现旧轴枚举与本机 FE01 效果有差异，也确认包层返回码可能在进入业务解码前被剥离。
增加可复现提取器和纯离线候选载荷工具，未修改任何 SDK/UI 运行时或发送允许列表；命令清单仍为 48 条，完整性条件仍为 false。
工具说明与不适用边界见 [MSDK_V4.md](../tools/research/MSDK_V4.md)。


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
