# 未通过项复测与关闭修复：0.7.35

Node/Python0.7.35；原生0.3.36/build39不变。延续用户已有实机授权；本轮没有新增运动、维护启动、设置写入、配对变更或未知命令。原始抓包和标识仍仅在ignored node/captures。

## 结果

| 未通过项 | 本轮证据 | 当前结论 |
|---|---|---|
| 关闭Unknown error | 精确定位unsubscribeAsync/stop_notify失败，后续disconnect成功；Node与Python均复现 | 修复默认macOS传输清理路径，见下文实机复测 |
| 手柄04:36 | Node与Python3.12各延长到10秒，均无关联响应；前后灵敏度读取成功 | 不是单纯超时时间太短或Noble独有问题；仍未通过，不改地址/降级ACK关联 |
| 主动调参状态04:6E | Node与Python3.12各10秒仍无响应 | 被动6E推送与主动查询分开；不拿缓存冒充查询成功 |
| 电机04:32批量 | 单Pitch/刚度成功；Node按轴4项、按参数3项、全12项均只收到首条；Python批量同样拒绝 | 本机多项请求不完整，继续使用已验证单项；不填默认值或发布半帧成功 |
| 参数订阅 | 单独MotorEnabled及PeripheralPosPitch各10秒，仍仅见已有abnormal/program通知，正常close | 对应新数据流未确认 |
| 系统/平衡寄存器 | 用户已确认重启且后续AUTO报告完成，再读仍为START1/TESTING64、三轴null | 可能是保留的请求值/不适用路径；不能据寄存器断定还在执行，也不能报任务完成；本轮没有重复启动 |

Roll停止后精度复测：约2°往返，原测试速度min0.025/max0.06/gain0.02的停止后误差+0.1°，更低速度min0.01/max0.025/gain0.012为−0.1°，均在0.5°内，回到各自起点附近后正常close。两次都是自动调参后的当前负载样本，不能抹掉调参前0.7°失败，也不证明默认min0.05/max0.18或全负载精度。

调参后的Pitch刚度本轮读到6，早先为41；用户已授权自动调参，这不是同值写回批次的结果。没有擅自把旧值覆盖回去。

## macOS关闭修复

Noble macOS后端和默认Bleak CoreBluetooth客户端，先停止主机运动、取消待处理任务并移除/隔离本地回调，再有界取消本客户端连接；不再额外发设备拒绝的通知关闭请求。Node其他适配器、Python注入客户端及非macOS平台保留显式取消通知。没有匹配Unknown字符串吞异常，真正stop/disconnect失败仍抛出。

Apple说明取消的是本地连接，其他App仍可保留底层物理链路。因此正常close证明本客户端清理，不能保证所有系统/其他App连接都消失。参见[Apple cancelPeripheralConnection](https://developer.apple.com/documentation/corebluetooth/cbcentralmanager/cancelperipheralconnection(_:))。本次没有通过取消配对或全局蓝牙开关规避问题。

实机：Node三个独立控制器连接/读取/close全部正常，坏帧0，managerStopped=true；随后三轮静止断线自动重连均速度0，最终close正常。Python3.12对照读取后的close由原先报错变为正常；Python3.8旧Bleak依赖的连接/反馈/灵敏度/close也通过，坏帧0。临时3.8读取脚本旧版本标签仍为0.7.34，实际直接导入本次0.7.35源码，不能把该标签当安装包版本。本次修复不改变DUML命令、参数含义、运动算法或其他端API。

回归覆盖：CoreBluetooth路径不调用通知关闭、断开错误仍传播、其他适配器/注入客户端取消通知错误仍传播、关闭后迟到反馈不发布。统一离线Node281项、Python3.8 SDK262/研究558、原生1562核心+301生命周期+3独立SDK+270GUI、类型/分层/签名构建通过；Python3.12 SDK262另通过。实际安装tarball281+严格类型、wheel262通过，导入路径和Node113文件/wheel40模块逐字节核对。完整交付见本次outputs记录。

仍未解决：手柄/6E主动查询响应、批量电机读取、系统/平衡真实完成、远端订阅生效、默认定位精度和原生程序/完整协议缺口。保持fullAcceptanceComplete=false及高级新增门槛false。恢复设置明确排除，Web已移除。
