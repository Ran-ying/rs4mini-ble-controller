# 单次命名参数订阅请求（0.7.26 / 原生0.3.26 build29）

设备 SDK 增加 `sendParameterSubscriptionRequest`，发送源 App 的04:12非空命名参数订阅报文。它是一次设备协议请求，不是主机后台订阅管理器或高级运动组合。

```js
gimbal.appCommands.useProfile('ronin-2.2.2');
const names = gimbal.appCommands.parameterSubscriptionKeys;
const sent = await gimbal.appCommands.sendParameterSubscriptionRequest({
  keys: ['UserProfile', 'ControllerMaxSpeedYaw', 'PeripheralPosYaw'],
});
```

应用仍从 `RS4Mini` 唯一入口调用。Web共享JS核心。Python为 `await gimbal.app_commands.send_parameter_subscription_request(keys=['UserProfile'])`，支持camelCase及两种命名的目录属性。原生 `RSGimbal` 继承 `appParameterSubscriptionKeys` 与 `sendParameterSubscriptionRequest:@{@"keys":@[@"UserProfile"]} completion:...`。

## 输入与固定源分支

keys必须是1..152项已知名称的数组（Python也接受tuple），重复名称去重并排序。禁止未知名称、原始频道/命令/端点、enabled、空集停止或定时刷新选项。目录返回新数组，提交请求前复制选择。三个端的152键目录与[固定源码目录](../tools/research/SUBSCRIPTION_CATALOG.md)逐项检查。

独立SDK明确采用固定res/DB.json已加载、HG724静态条件为true的源分支；21个元数据条件键与2个型号条件键分别在结果的metadataConditionalKeys/modelConditionalKeys报告。它不模拟手机App异步初始化，不依赖其缓存，也不证明真实App构造时捕获了哪些索引。详见[初始化研究](../tools/research/SUBSCRIPTION_INIT.md)。存在别名的不同键共用频道位；不是152条独立BLE命令或152项本机能力。

## 报文和事务

固定APP发送到CENTER/type5,id7（receiverByte=229/E5），commandSet4、commandId18/0x12、flags=0，无ACK请求。各组为commandByte、最高频道号、LSB优先位图，按16/50/102排序；组内频道去重。选择全部键时36字节业务体、121个命令/频道对。完整DUML报文仍按20字节分包。

所有端先发送三条中位速度帧，独占既有操作槽至本地写入完成。与主机运动冲突时报busy。发送前取消不再发送订阅；已开始的报文完成分包后清理。取消、超时或断线不发送反向订阅、不回滚、不自动重发，重连不恢复选择。

Node/Python使用已有ioTimeoutMs限制单次GATT写入；写入失败或超时使会话失效。原生沿用3秒写入进度看门狗及前导结束后的固定3秒事务期限；超时清理仍持有操作槽，实际链路失效也会清除会话。Web blur调用停止并取消此独占操作。各端都不等待不存在的ACK。

## 返回和未验收项

结果包含requestedKeys、sourceGroups（频道/最高频道/bitmapHex）、条件键列表、requestBodyHex、固定sourceCase与receiverByte。sent=true只说明本地写入完成。

acknowledgementRequested、acknowledged、sourceAppInitializationVerified、targetRoutingVerified、notificationStreamVerified、remoteSubscriptionStateVerified、freshStatusVerified、deviceVerified、physicalCompletionVerified均为false。

不主动刷新、维持引用计数、推断租约或提供远端停止。该请求不关联下一条状态、不填充缓存，不改变姿态/关节。已有04:24/66等候选通知继续独立处理；尚未为所有订阅键提供类型化通知。真实路由、频率、通知布局、停止条件与本机接受/效果仍需验收，全命令和新增高级功能门槛保持false。没有执行硬件测试。
