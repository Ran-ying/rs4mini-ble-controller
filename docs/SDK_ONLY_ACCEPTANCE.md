# 三端 SDK 直接可用性验收：0.7.36

最新本轮：[Node连续非校准验收](SDK_NODE_CONTINUOUS_ACCEPTANCE.md)。仅Node硬件：普通119/119、小幅速度与自动重连9/9通过；实验区只读5/6，其中position仍超时。完整回中待单独授权；调参/水平校准按用户要求不重跑。运行时0.7.38/原生0.3.39不变，以下旧轮次记录保留历史。

最新0.7.38 / 原生0.3.39 build42：移除旧系统与旧平衡测试共4个公开方法后，直接SDK基础复测Node24/24、Python3.8/3.12各24/24、原生25/25全部通过。维护能力的三端逐项实测见[验收队列](SDK_ACCEPTANCE_QUEUE.md)；下文0.7.36为此前检查点，不能据基础探针声称所有未知协议完整。

维护能力本轮进展：[逐项实机验收](RETAINED_MAINTENANCE_ACCEPTANCE.md)。AUTO完成已由用户确认；系统校准和平衡测试均无设备反应，未通过。微调正核对可见效果。

Node/Python0.7.36，原生0.3.37/build40。按用户决定移除手柄查询、主动调参状态查询及Python别名/原生selector/对应面板入口；被动calibrationStatus保留。电机多项改为逐项请求并完整汇总。

本轮只测试SDK：Node/Python直接创建BleDevice；macOS无界面进程只链接RSBleDevice、RSControlCore、Foundation/CoreBluetooth，没有RSGimbal、运动模块或AppKit。入口见[仅SDK测试](../tools/hardware/README.md)，机器结果为`protocol/SDK_ONLY_ACCEPTANCE.json`。

| 运行环境 | 检查项 | 全量/按轴/按参数/单项电机读取 |
|---|---|---|
| Node | 24/24通过 | 12 / 4 / 3 / 1，完整 |
| Python3.8 | 24/24通过 | 12 / 4 / 3 / 1，完整 |
| Python3.12 | 24/24通过 | 12 / 4 / 3 / 1，完整 |
| macOS原生SDK | 25/25通过 | 12 / 4 / 3 / 1，完整 |

连接、新姿态/机械关节、命名参数读取、degree-info、停止和关闭/断开均通过。检查数量包含生命周期/层隔离探针，不是SDK方法总数。原生额外检测蓝牙就绪/显式来源，而Node/Python检查解码器计数，因此数量略有差异。原生没有close方法，检验的是公开disconnect后的状态。

电机读取每次只请求一个索引并严格匹配ACK。单项保留真实AppParameterReply，增加readMode:'single'；多项完整返回readMode:'sequential',atomic:false,values,parameters,replies，不制造顶层ACK/message/bodyHex，也不在中途失败时返回部分数据。总timeoutMs覆盖整个循环；取消/NACK/超时立即停止后续项。详见[电机契约](APP_MOTOR_TUNING.md)。

本轮没有设置写入、运动、校准、平衡或恢复设置，也不验GUI。0.7.35三端灵敏度1写回1/ACK/回读通过作为历史证据保留，不能把它计入本次只读检查。两个退役查询的失败证据保留在Git历史和研究文档，不再是当前SDK可调用能力。

结论：当前这组直接SDK可用性检查全部通过；完整未知协议、其余所有写操作、固件任务物理完成、跨负载运动精度仍是独立验收范围，fullAcceptanceComplete与高级新增门槛仍false。所有控制客户端已关闭/断开。

离线回归：Node279、Python3.8/3.12各260、研究558、原生1562核心+317生命周期+3独立SDK+260表单适配，以及严格类型/边界/签名构建通过。实际安装tarball279+类型、wheel260通过，导入路径核对；Node113文件、wheel40模块、原生ZIP3文件与交付源码/签名构建逐字节一致。本轮未启动GUI，原生表单检查只是离线编译回归。
