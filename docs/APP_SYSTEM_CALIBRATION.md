> 已退出公开SDK（0.7.38）：Node复测无实际功能效果后，用户要求移除启动和状态方法。本文只保留历史协议研究，以下示例不适用于当前SDK。水平校准请使用现有sendComponentCalibrationRequest(sourcePart:AUTO)。

# system_calc 自动校准接口（0.7.8 / 原生0.3.8）

本接口沿App的 `startGimbalAutoCalibration()` 路径封装，和已有的电机自动调参 `sendAutoTuneRequest()` 分开。应用仍只创建RS4Mini/RSGimbal，设备SDK复用同一连接/队列/操作协调器，要求显式ronin-2.2.2来源配置。

尚未证明这条继承路径就是RS4Mini固件/UI中的“水平校准”，因此不命名为水平校准，也不宣称该缺口已全部解决。

## 接口与结果

```js
// 只供明确授权的实机会话；默认测试不执行这些调用。
gimbal.appCommands.useProfile('ronin-2.2.2');
const ack = await gimbal.appCommands.sendAutoCalibrationRequest({timeoutMs:3000});
const report = await gimbal.appCommands.getAutoCalibrationStatus({timeoutMs:3000});
```

Python提供相同camelCase方法及 `send_auto_calibration_request()` / `get_auto_calibration_status()` 关键字接口。原生RSGimbal继承 `sendAutoCalibrationRequestWithTimeoutMs:completion:` 和 `getAutoCalibrationStatusWithTimeoutMs:completion:`。

启动固定向普通用户参数04:0F发送 `24 01 01`，flags40，即system_calc/index36/size1/值1。不能传任意值、轴或start:false，不提供写零中止。先停止主机连续运动，独占操作槽到关联ACK/超时/取消；成功返回AppCommandReply和requestedValue1。ACK后释放主机槽，不等待固件完成，不自动重发或修改反馈缓存。

读取使用04:10、载荷24，按index36/size1上下文解析。返回AppParameterReply与systemCalibration：

```js
{ rawValue:3, state:'SUCCESS' }
```

0 DEFAULT、1 START、2 FAIL、3 SUCCESS；4..255保留原始值，state为null。写入资源范围为0..1，**不能用该范围截断读取状态2/3**。返回记录第二头字节保留为headerByte，不当作实际宽度。ACK返回码与状态是不同层，SUCCESS也没有程序ID来关联本机请求；physicalCompletionVerified仍false。

## 与已有自动调参的区别

| 接口 | 线上路径 | 状态含义 |
|---|---|---|
| sendAutoCalibrationRequest/getAutoCalibrationStatus | 普通用户参数0F/10、system_calc/index36 | DEFAULT/START/FAIL/SUCCESS原始枚举 |
| sendAutoTuneRequest/queryCalibrationStatus、calibrationStatus通知缓存 | 6A请求、6E查询/通知 | 调参状态及百分比候选记录 |

两者不共享状态缓存、进度或完成判断。新接口不根据6E响应更新system_calc状态，也不实现自动轮询或等待完成任务。App自身30秒轮询和超时后的本地布尔值不能当作固件物理结束证据，因此没有移植为SDK完成承诺。

## 生命周期与验收边界

timeoutMs默认3000，范围>0..60000；启动响应截止时间从停止前置步骤后开始，停止/I/O沿用已有有界清理。Node/Python读取可与主机运动共存，原生读取独占并先发中位帧；不因此保证固件校准期间运动可安全并行。

stop/断连/Web失焦取消待处理主机事务，不保证固件校准中止，不发送未经证实的中止值或回滚。没有新增高级运动任务或面板按钮，没有扫描、连接、运动、启动UI或执行App。

来源为HG724→HG702→Ronin2→RoninBase继承的自动校准方法，数组槽22解析为system_calc，资源唯一命名记录index36/size1/type0。继承不证明目标固件或App UI启用支持；水平校准身份、实机接受/报告/物理完成/中止仍待验收。全协议和高级新增门槛仍false。

静态复现工具 [ronin_system_calibration_trace.py](../tools/research/ronin_system_calibration_trace.py) 固定APK/恢复视图哈希，核对数组槽、资源、继承、请求、读取回调与状态枚举，保存14个方法指纹。证据：[ronin-system-calibration-evidence.json](../protocol/research/ronin-system-calibration-evidence.json)。

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_system_calibration_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --dex work/research/code-final/business-05-code-restored.dex \
  --output work/research/reproduced-system-calibration.json
```

离线测试覆盖写入与状态范围分离、所有未知字节保留、6E错误命令关联、请求/读取向量、畸形上下文、非零ACK、互斥、取消/超时及无重放/无虚构中止。测试通过不提升为本机验收。


后续[校准入口条件审计](../tools/research/CALIBRATION_ENTRY.md)已分开页面systemCalibration→04:08/GYRO与本SDK参数36路径，并核对30进度的源UI百分号显示；这不改变本机单位、请求关联或物理完成标志。当前没有开放08触发。
