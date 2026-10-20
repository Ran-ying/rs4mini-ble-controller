# 保留维护能力逐项验收（2026-10-20，SDK0.7.37 / native0.3.38 build41）

本轮直接调用设备SDK，不使用GUI。用户要求删除订阅、手柄/摇杆写入、恢复设置三个类别；Node/Python/macOS公开入口、Python别名、类型声明、macOS动作与示例同步移除。保留被动状态及程序状态单次请求，离线协议编解码仍作研究证据。完整协议与高级开发门槛保持false。

| 保留项 | 本轮证据 | 结论 |
|---|---|---|
| 自动调参完整运行 | Processing到Complete100；12电机参数前后读取成功；用户确认“云台校准完成”，手动确认后返回正常界面 | 本次运行完成已验证；设备确认步骤仍需手动；保存/重启持久化未证明 |
| 自动调参停止请求 | 4秒时Processing30，发送false后约40ms收到Complete100；用户看到“云台校准完成”并确认返回 | 请求和终态已验证；缺少独立中止标志及振动停止观察，不能宣称中止语义验收通过 |
| AUTO部件校准 | ACK后04:30 PROCESSING到COMPLETE100；同时收到独立调参进度；用户确认“校准完成，已经返回” | 本次实际完成通过；不合并两种进度缓存，不承诺远端中止或自动确认 |
| 系统校准 | ACK成功；60次逐项状态读取始终START1；用户确认屏幕/机身没有反应；已正常关闭 | 不通过：状态值不是启动/完成证据，不重复盲启；需重新核对目标型号入口 |
| 平衡测试 | ACK成功；60次读取均TESTING64，三轴字段全0/null；用户确认没有反应，正常关闭 | 不通过：不能用起始寄存器值证明实际测试 |
| Pitch/Roll微调 | 每轴+0.2°后−0.2°均ACK0；Pitch关节−0.9→−0.7→−0.9，Roll−0.5→−0.2→−0.4；用户Pitch肉眼看不清 | 有可测反馈变化；Roll经用户确认有变化无异常，Pitch肉眼仍不清楚，不承诺精度/绝对或增量语义/持久化 |

原始报文与设备身份仅存本地忽略目录node/captures，不提交Git。每次任务连接最终关闭；未确认前一任务结束，不启动下一项。停止普通速度不等于中止固件校准。

系统校准调查：SDK沿继承startGimbalAutoCalibration写system_calc/index36；厂商页面systemCalibration走04:08/GYRO05，HG724普通入口隐藏，先进校准走04:08/AUTO00。不能按相似命名改用GYRO或把AUTO完成覆盖参数36状态。现有静态证据见tools/research/CALIBRATION_ENTRY.md；不把当前无反应推断为固件绝对不支持。

补测±1.0°：Pitch两轮ACK及关闭通过，最近一轮机械Pitch−0.9→0.0→−0.9；用户仍肉眼看不清。Roll一轮ACK及关闭通过，机械Roll−0.5→+0.7→−0.4，用户确认“有变化无异常”。误差和读数分辨率保留，不能把这些样本升级为所有负载精度保证或偏移持久化。

离线：Node250、Python3.8/3.12各231、研究558、原生1562核心+265生命周期+3独立SDK+230GUI适配，严格TS、分层门槛和签名构建通过。已移除发送接口的生命周期测试由入口不存在检查取代；其离线协议向量仍保留。不运行实时GUI。

## 下一步入口定位

2026-10-20查阅[DJI RS 4 Mini官方用户手册](https://dl.djicdn.com/downloads/DJI_RS4_Mini/20250220/UM-mini/RS4_Mini_User_Manual_en.pdf)，屏幕首页区分Auto Tune与以颜色表示的Balance Status；系统设置另列Horiz Calibration。该说明不能提供BLE命令或证明旧参数37启动有效，也不能把被动平衡颜色视为旧三轴测试报告。

[DJI官方帮助](https://repair.dji.com/help/content?customId=01700007797&lang=en&paperDocType=ARTICLE&re=US&spaceId=17)另列Gimbal Auto Check，并区分调参和系统校准。自检、水平校准、AUTO部件校准及system_calc不能按文字相似直接互换。

下一步只请用户查看屏幕有无水平校准入口，不启动额外任务；再与固定APK的实际调用/型号条件及传输证据对齐。未建立路径之前，不盲发04:08/GYRO05、不改用04:40、不制造成功或支持/不支持结论。所有本轮BLE客户端均已关闭。

## 用户补充与名称纠正

用户已在设备系统设置找到“水平校准”，但对先前运行的判断来自动作，不记得当时具体文字或轮次；因此没有确证AUTO00就是屏幕自动水平校准。

| 实际SDK调用 | 当前可用名称 | 验收边界 |
|---|---|---|
| sendFineTuneRequest(axis:roll) | Roll手动水平微调 | 用户确认±1°有变化无异常；不能因此称自动水平校准完成 |
| sendFineTuneRequest(axis:pitch) | Pitch俯仰微调 | ACK及机械角正反变化，用户肉眼看不清 |
| sendComponentCalibrationRequest(sourcePart:AUTO) | AUTO传感器/部件校准 | 04:30 COMPLETE100及用户完成确认；与屏幕自动水平校准的等同性待核 |
| sendAutoCalibrationRequest() | 旧system_calc参数校准请求 | 本机无可观察效果；不是已验证的屏幕水平校准入口 |

自动调参6A调整电机；传感器AUTO08、Roll手动水平微调07、旧system_calc参数36分别记录，不混用名称或完成证据。不能概括为“水平校准都没有做”，也不能反向把可见倾斜动作当作自动水平校准身份的证明。下一步优先定位屏幕自动水平校准对应路径；不重复无反应的旧参数请求。
