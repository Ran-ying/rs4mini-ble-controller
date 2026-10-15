# 剩余非相机协议的静态研究记录

2026-10-15。在完成 0.7.0 扩展后，继续检查 [DJI 官方 Ronin 下载页](https://www.dji.com/downloads/djiapp/dji-ronin) 提供的 Android 文件。
下载文件名标为 2.2.2 / 7096，SHA256：

`4ef0aa1e351990168a522500728790e22794618b0bcbd4c6277c7375148dc4f4`

未安装、未运行 APK，也没有接触稳定器。文件和临时解析脚本在被忽略的 `work/research/`；不放入源码包或 Git。

## 已观察到的线索

- `classes.dex` 长 69,867,108 字节，标准头部字符串池只有 346 项，含 `com/AppGuard/AppGuard` 壳类。
- 尾部 `dexdata0` 业务负载仍能找到下列类名，但正常头部并未暴露这些类的完整方法/字段表。
- 原生 `libgimbal-lib.so` 中检查到的是跟踪控制相关符号，没有据此推导稳定器非相机参数。

可继续定位的业务类：

| 目标 | 类名线索（`dji.midware.data.model.P3`） |
|---|---|
| 原生绝对角/速率 | `DataGimbalAbsAngleControl`、`DataGimbalAngleControl` |
| 单轴重置/模式 | `DataGimbalNewResetAndSetMode` |
| Ronin 用户参数 | `DataGimbalRoninGetUserParams`、`DataGimbalRoninSetUserParams`，后者有 `WorkMode` / `HoldType` 嵌套类 |
| 校准/进度 | `DataGimbalCalibrate`、`DataGimbalAutoCalibration`、`DataGimbalGetPushCalibrationStatus` |
| 平衡状态 | `DataGimbalBalanceAdjust`、`DataGimbalGetBalanceAdjustPushInfo` |
| 额外反馈/电量 | `DataGimbalGetPushUserParams`、`DataGimbalPushBatteryInfo` |
| 原生动作程序 | `DataGimbalSetDelayTimelapseParams`、`DataGimbalGetPushTimelapseStatus`、`DataGimbalGetPushPanoramaStatus` |

这些只是应用包含的共同类名，**不能证明 RS 4 Mini 会走对应路径，也不能据此填入命令 ID、字段偏移或枚举值**。
目前没有完成业务负载的结构还原，没有提取到可直接采用的 RS 4 Mini 参数表。因此本轮不扩大已列明的实验命令允许列表。

## 下一步证据

继续静态还原时，需要同时证明请求构造、响应解析和 RS 4 Mini 的型号分支。仅恢复字符串或使用无人机/Osmo 的同名类不足以确认。
现场条件具备后，可在 Ronin App 中一次只改变一个非相机设置，记录前后屏幕状态与受控 BLE 样本，匹配这些候选类和 DUML 字段。
不得批量探测、重放校准或恢复默认参数命令。采样与运动仍遵循 `HARDWARE_CHECKLIST.md`。
