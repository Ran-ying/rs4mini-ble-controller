# 离线队列 E：会话版本 / 状态关联

2026-10-20。工具 [ronin_queue_e_session_version_trace.py](ronin_queue_e_session_version_trace.py)，证据 [ronin-queue-e-session-version-evidence.json](../../protocol/research/ronin-queue-e-session-version-evidence.json)。接续 [ACTIVATION_RECEIVE.md](ACTIVATION_RECEIVE.md)、[ACTIVATION_ENTRY.md](ACTIVATION_ENTRY.md)。

状态：**`statically_exhausted_needs_hardware`**。

## 静态已证

- `DataCommonActiveGetVer.doPack` 使用 `TYPE.GetVer`；`setRecData` 按设备类型调用 `DataGimbalActiveStatus.setVersion` 等——**版本查询响应会改写激活单例版本字段**。
- `DataAbstractGetPushActiveStatus.setPushRecData` **先** `setRecData` **再** 长度≥11 / ACK 门控——短包或版本 ACK 若走混合路径，可能先覆盖缓存字节。
- 离线 `activation_version_ack_view` 仅适用于**显式版本查询上下文**；失败 ACK 不得解析出版本名。
- CENTER ActiveStatus 类存在，与 GIMBAL GetVer 路由需分开（既有 ENTRY 专题）。

## 未证

- 本机会话表选择、扩展 CmdSet、加密终态、请求-响应关联器行为。

不开放激活写入；不把版本查询体混入激活状态。
