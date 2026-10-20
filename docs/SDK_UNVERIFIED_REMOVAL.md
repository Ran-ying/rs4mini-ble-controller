# 移除未验收入口：0.7.39

2026-10-20，用户要求将单列的未验收项目从代码移除。Node/Python0.7.39、macOS0.3.40/build43同步以下变更。

| 移除项目 | 公开入口及行为 |
|---|---|
| 实验区位置查询 | `experimental.query({kind:'position'})`及Python等价调用不再接受该kind；原生实验JSON入口同样在发送前拒绝。正常`getAttitude()`和`getJointAngles()`保留 |
| 教程状态 | 移除`tutorialStatus`及事件`tutorial` |
| 外部控制状态 | 移除`externalDeviceStatus`及事件`externalDevice` |
| 外设状态 | 移除`peripheralStatus`及事件`peripheral` |
| 电池状态候选 | 移除`batteryStatus`及事件`battery` |
| 手柄/摇杆状态 | 移除`handheldStickStatus`及事件`handheldStick` |
| 用户参数状态 | 移除`userParameterStatus`及事件`userParameters`，普通命名参数的主动读取/写入保留 |

Python的六组snake_case属性、原生对应`app…Status`属性、内部缓存、接收分派和GUI状态快照同步清理。TypeScript删除这些公开属性和状态接口，`AppStatus`仅保留四种已实测的事件。原生GUI命名操作仍32项，状态快照由10类缩减为4类。

当前App来源保留：`calibrationStatus`（电机调参）、`sensorCalibrationStatus`（水平校准）、`abnormalStatus`、`programStatus`。前两项沿用之前完成及用户确认的证据；本轮没有启动校准。微调、普通设置、速度控制、停止、回中、反馈和重连没有改动。

移除的六类报文不再被App来源SDK缓存或发布事件，仍可从通用原始消息回调查看。纯codec、共享向量和研究文档作为离线历史保留，不再作为当前App来源SDK功能；其他型号实验区的历史原始codec也不提升为RS4 Mini已验收功能。没有新增发送、参数猜测或高级功能，完整协议清单和高级开发门槛仍false。

## 验证

新增回归验证六个公开入口及Python别名不存在、六种完整源报文只进入原始回调、不产生SDK事件/写入、不结束待处理查询；`position`在发送前拒绝。原生验证属性不存在、原始消息继续传递、事件不发布和位置查询不发送。保留纯codec测试，以及调参/水平校准和异常/程序状态的生命周期检查。

离线Node228、Python3.8与3.12各209、研究558、原生1562核心+236生命周期+3独立SDK+210GUI适配检查，以及严格TypeScript、分层和签名构建通过。机器结果见[清理验收记录](../protocol/SDK_SCOPE_CLEANUP_ACCEPTANCE.json)。安装后的tarball228及严格类型消费者、wheel209通过，实际导入位置已核对；Node114文件、wheel40模块、原生ZIP3文件与当前源码/签名构建逐字节一致。验收日志和安装包在工作区outputs；Node直接设备SDK只读基础24/24、保留实验区查询/解码/关闭5/5实机复测通过；不含运动、设置写入、调参或校准。所有客户端正常关闭。

此前[连续验收](SDK_NODE_CONTINUOUS_ACCEPTANCE.md)及机器记录按当时版本保留，包括position超时和无通知事实；删除接口不会把历史失败改写为通过。当前去除这些入口后，现有常规SDK继续按已测数值、负载和平台范围使用，不宣称厂商全部BLE命令已实现。
