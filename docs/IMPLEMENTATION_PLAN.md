# 0.6.0 开发与验收计划（历史阶段）

本文件记录 0.6.0 阶段；当前状态见 [PROJECT_STATUS.md](PROJECT_STATUS.md)，后续扩展见 [EXPANSION_PLAN.md](EXPANSION_PLAN.md)。

用户要求继续完成未完成代码，交付 Node 及其他现有版本。离家期间只运行离线测试；实机验证统一登记后等待用户回来。

## 代码验收范围

- [x] Node：运动操作所有权；停止期间互斥；可取消的限时运动；写入中停止；总超时归一化；多轴逐轴容差。
- [x] Node：全连接阶段截止时间；关闭/断开取消连接；迟到连接清理；重连监听移除；通知回调异常隔离。
- [x] Node：故障路径与类型消费方测试、版本/锁文件/API/示例同步。
- [x] Python：完成反馈解码、位置闭环、生命周期与运动调度；保留现有两种命名；对齐半步舍入；离线回归测试。
- [x] Web：完成反馈解码、位置闭环、生命周期与运动调度；连接失败/断线/页面失焦清理；离线回归测试。
- [x] macOS：反馈显示、低速关节目标控制、连接截止时间、运动/停止调度、失焦与退出清理、原生离线验证。
- [x] 四端文档、功能矩阵、统一实机验证清单与可下载源码交付。

协议不新增未经验证的绝对角命令、单轴回中或相机控制。意外断线后不自动恢复运动；重新连接需显式调用。固件物理急停、四元数坐标约定和硬件精度不能由离线测试证明，列入验证边界。

## 当前进展

- 部署基线：Node 0.5.0；Python 0.2.1；原生和 Web 为早期基本速度控制。
- 部署前的离线检查已通过；2026-10-15 Node 基线连接与 5 秒反馈采样通过。
- 本计划开始后不再连接或移动硬件。

## 验收证据与交付

- 运动/连接回归：`node/test/controller.test.js`、`node/test/noble-adapter.test.js`。
- Python：`python/tests/test_controller.py`，含协议重组、半步、取消、迟到连接及两种 Python 运行时验证。
- Web：`web/test/`，含模拟 GATT 与真实页面事件处理器的假 DOM 测试。
- 原生：`macos/test-core.m`、`macos/test-gimbal.m`，由 `macos/test.sh` 运行，不创建实际蓝牙管理器。
- 类型、打包和统一检查入口：`node/examples/types-smoke.mts`、`tools/check-offline.sh`。
- 已生成 Node tarball、Python wheel、原生应用 ZIP 和四端完整源码 ZIP；交付文件位于本聊天 outputs。
- 实机行为和可视布局检查按 `HARDWARE_CHECKLIST.md` 等待用户回家，不作为本轮已验证结果。
