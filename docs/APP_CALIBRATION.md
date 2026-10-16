# 当前 App 自动调参请求与校准状态（0.7.5 / 原生 0.3.5）

这是设备 SDK 的请求和反馈封装，应用继续只使用 `RS4Mini` / `RSGimbal`。必须显式选择 `ronin-2.2.2` 来源。SDK 没有等待固件调参完成的高级任务，未启动硬件或执行厂商程序。

## 实际型号路径

HG724 继承 HG702，后者覆盖 Ronin2 父类的 `startAutoTune()`。父类使用命名参数写入；HG702 实际构造 `DataGimbalCalibrate`，布尔字段传 true，再发送 `04:6A`，载荷 `00 01 01`。该请求的 NEEDACK 为 NO，不能等待一个源码未请求的 ACK 或把父类路径当作当前型号行为。

同一打包类的布尔 false 编码为 `00 01 00`；这里只确认字段与源码载荷，没有验证它能否在本机中止已经运行的调参。类名中的 Calibration 与 HG702 的 AutoTune 业务调用分别记录，不把它扩展为水平校准或所有校准类型。

## 请求接口

Node / Web：

```js
// gimbal 为应用已有对象；以下会向已连接硬件发送请求，非离线示例。
gimbal.appCommands.useProfile('ronin-2.2.2');
const sent = await gimbal.appCommands.sendAutoTuneRequest({ start: true });
```

`start` 必须为布尔值；没有隐式默认或数字动作码。操作先停止连续主机速度，取得原有操作槽，通过共享连接/序号/队列发送 `04:6A`，flags为0。仅在本机写入完成后释放操作槽，返回：

```js
{ profile: 'ronin-2.2.2', sent: true, requestedStart: true,
  acknowledgementRequested: false, acknowledged: false,
  deviceVerified: false, physicalCompletionVerified: false }
```

返回值表示本机发送。固件程序可能继续执行；SDK不在整个调参期间持有运动槽，也不自动按通知推断程序完成或允许下一步运动。写入仍由既有 I/O 截止时间约束，不重发、不在重连后恢复。输入错误在停止/写入前拒绝。

`stop()` 取消主机操作并清理待发帧、发送既有中位停止。已经开始的帧会完成分片，已发送请求不承诺回滚或物理中止；`stop()` 不自动追加一条 `04:6A false`。调用者可显式发 `start:false` 请求，其设备端中止效果尚待实测。发送后不要据这个返回值认定设备已经静止。

Python：`await gimbal.app_commands.send_auto_tune_request(start=True)`，同名 camelCase 方法也可用。原生：`[gimbal sendAutoTuneRequest:@YES completion:...]`，只接受布尔 NSNumber；背压时持有操作槽直到请求队列写完，completion 主队列异步返回。原生固定写入截止时间3秒，Node/Python使用已有 ioTimeoutMs。

## 状态查询与通知

| 入口 | 行为 |
|---|---|
| `await gimbal.appCommands.queryCalibrationStatus({timeoutMs?})` | `04:6E` 空载荷、flags40；等待同一会话/序号/端点/命令/响应位的响应，默认3000ms，范围大于0且不超过60000ms |
| `gimbal.appCommands.calibrationStatus` | 最近一次有效推送快照或 null；读取不发送命令 |
| `gimbal.onAppStatus = status => ...` | 显式来源配置下的被动状态回调，观察者错误隔离 |

Python 对应 `query_calibration_status(timeoutMs=...)`、`calibration_status`，保留 camelCase 属性/方法；事件为 `gimbal.onAppStatus`。原生为 `queryCalibrationStatusWithTimeoutMs:completion:`、只读 `appCalibrationStatus`、`appStatusHandler`。原生查询沿用独占操作槽和中位停止，Node/Python查询可与运动共存；`stop()`取消原生查询，独立Node/Python查询通过超时/断连结束。

查询响应先按当前 App 返回码规则剥离首字节，非0抛设备错误。之后解析业务记录，结果放在 `reply.calibration`。仅ACK没有记录时返回空记录和 null 状态/百分比，不制造“未开始/0%”。查询结果不写入未关联的推送缓存。请求不自动重试，App 中的重发次数没有直接照搬到SDK。

被动通知必须来自 sender04→receiver02、set04/id6E且没有响应位，直接解码记录，不剥离返回码。缓存含来源、到达时间戳和 `physicalCompletionVerified:false`；收到标记为 Complete 的消息也不能证明它属于刚才那次请求，因为记录没有程序ID或请求序号关联。相同会话中其他操作/控制端或早先程序的通知无法归属到一次请求。

## 记录格式

业务体是 `tag:uint8, size, value` 连续记录，首个tag须为0或1。当前App以有符号字节读取size；SDK只解释0..127长度，其他长度保留整包原始消息供研究，不猜宽记录。所有记录先验证完整边界；tag0至少2字节，value第0字节为状态、第1字节为百分比原值。重复tag0使用最后一条完整记录，其余记录和额外尾字段保留 `rawHex`。

| rawState | App 原枚举 |
|---|---|
| 0 | UnStart |
| 1 | Processing |
| 2 | Complete |
| 3 | Failure |
| 255 | UnKnown |

其他状态以 `state:null` 和 `rawState` 保留；百分比超过100时 `percent:null`，保留 `rawPercent`。未知记录不推断含义。仅未知记录、空记录、截断或错误端点/响应位不会把缓存重置为零；原始消息仍走既有消息回调。切换来源、重选配置或断连清理缓存。Node/Python状态与事件数据均复制；原生结果使用不可变结构，观察者异常被记录并隔离。

合成向量：通知业务体 `00 02 01 28` 是 Processing/40；查询响应载荷 `00 00 02 01 28` 的第一个00是返回码，其余才是记录。它们没有发送到设备。

## 证据与剩余验收

[ronin-calibration-evidence.json](../protocol/research/ronin-calibration-evidence.json) 固定16方法指纹、HG702覆盖路径、NEEDACK与状态枚举；原始APK/恢复视图的SHA256均校验，不执行厂商代码、不输出完整指令体。

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_calibration_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --dex work/research/code-final/business-05-code-restored.dex \
  --output work/research/reproduced-calibration-evidence.json
```

需用户返回统一验证：命令接收/效果、start:false中止、状态查询实际响应、推送启停条件、运行中其他运动命令行为、停止后的读数、未知记录及固件差异。不要用主机停止帧或一次Complete报告替代这些证据。电机数值调参、平衡测试、水平校准及其他底层命令仍未完成，高级开发门槛继续为false。


## 0.7.8 system_calc自动校准

四端新增独立的普通0F/10/index36固定启动1和状态读取，与6A/6E自动调参分开。读取状态2/3不受写入范围0..1限制，未知值保留raw/null；ACK/报告不代表本次物理完成，取消不保证固件中止，无虚构写零停止。Node108/Web14/Python各86/native75+101+3/research45，类型/边界/构建通过。尚无水平校准身份或本机验收，未操作硬件/UI或新增高级任务。详见 [APP_SYSTEM_CALIBRATION.md](APP_SYSTEM_CALIBRATION.md)。
