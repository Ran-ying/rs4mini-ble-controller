# 微调、手柄与用户参数保存/重置的静态审计

2026-10-17，SDK0.7.14 / 原生0.3.14。本文工具固定66方法指纹、字段和继承，自身不提供SDK或传输。四端SDK接入手柄只读查询与Pitch/Roll微调请求，其他动作尚未封装；未执行厂商代码或操作硬件。来源为固定Ronin 2.2.2/7096 APK与恢复bank05；保存调用者另核对bank03。

## 微调04:07

DataGimbalRollFinetune的两字节体为signed value低字节、轴cmdValue。源码轴值ROLL=0、PITCH=2、YAW=4；Pitch/Yaw的枚举ordinal1/2不能用于线上轴值。HG724继承解析到DJIGimbalAbstraction的fineTuneGimbalPitchInDegrees/fineTuneGimbalRollInDegrees；尚未定位相同方式的Yaw微调调用，不声明Yaw不支持。

源码微调参数范围比较为-2..2度，经float32乘10、float-to-int向零截断，再取字节；不作为实际移动量/累计偏差或moveTo关节目标。离线例：Pitch -1.29→f402，Roll +1.29→0c00；近边界须保留float32步骤，不能换成四舍五入。Roll另检查needPauseStabilization，物理暂停/前置状态、单位实际效果与本机接收仍未验收。离线工具拒绝非法输入，不复制源方法在报告非法参数后可能继续打包的控制流。

## 手柄04:35/36

04:36空体查询；以下偏移是去掉返回码后的业务体，不是原始BLE payload偏移。最少8字节，原始值和额外字节保留。

| 偏移 | 源getter | 类型处理 |
|---|---|---|
| 0 | getDualChannelEnable | 原始整数，ControllerMode源码ONE_AXIS0/TWO_AXIS1/UNKNOWN255 |
| 1 | getTiltDirection | 原始整数 |
| 2 | getPanDirection | 原始整数 |
| 3 | getProfile | 原始整数，不与table_choice或MovementSettingsProfile自动等同 |
| 4 | getPitchFree | 原始整数 |
| 5 | getZoom2SpeedEnable | 保留原字节，源返回值只看bit0 |
| 6 | getRotationFocusEnable | 保留原字节，源返回值只看bit0 |
| 7 | getCellphoneSensorDisable | 保留原字节，源返回值只看bit0 |

当前范围不增加相机/手机传感器控制；后三个字段只作为源布局事实记录。HG724继承的ControllerMode和Pitch/Roll/Yaw反向方法解析到DJIGimbalHandheldAbstraction，不能因类名Handheld就判断为其他产品或本机已实测支持。

04:35依次打包mJoystickDualChannelEnable、mTiltDirection、mPanDirection、mProfile、mPitchFree、mZoom2Speed、mRotationFocusEnable、mCellphoneSensorDisable，每项低字节。新对象8字段均255；doPack后reset只重置前6项，后2项保留上次对象状态。离线非相机patch示例只允许前3个已核对0/1选项，未指定字节填FF，例Pan方向1→ffff01ffffffffff。这只复现源构造，不证明固件把FF理解为“不修改”，也不保证保留其他位或跨端对象复用安全；手柄写入SDK封装仍待完成。

## 用户参数重置04:13

loadFactorySettings沿HG724继承链解析到通用基类，最终使用DataGimbalResetUserParams。doPack检查的是PlatformType；HG724条件的if-eq实际跳到三字节构造，载荷010001。其他未命中平台分支可能为空体；不能复用空体或把GimbalComponentType枚举103当PlatformType。

命令名和源方法名不能证明实际恢复哪些参数、是否影响持久化、是否重启或物理动作。尚未开放SDK重置接口，没有试探发送，也不把ACK当成已恢复出厂设置。

## 保存04:11

DataGimbalSaveUserParams的源doPack为空，start请求ACK；仅从类可构造空体。固定bank05/bank03扫描未发现外部直接调用该类方法；扫描范围不是全App，更不是固件能力否定。缺HG724业务调用与实际持久化证据，因此仍不暴露saveSettings或宣称参数保存完成。

## 复现和验收

工具ronin_controls_trace.py核对固定APK/SDK/UI哈希、实际继承、轴枚举、命令ID、手柄每个字节目的位置、默认/重置字段，以及HG724重置分支真实PC跳转。输出protocol/research/ronin-controls-evidence.json；ronin_controls_payloads.py只有离线body核对，不编码DUML帧、不导入SDK/UI或提供传输。

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_controls_trace.py --apk work/research/dji-ronin-2.2.2.apk --sdk work/research/code-banks/business-05-code-restored.dex --ui work/research/code-banks/business-03-code-restored.dex --output work/research/controls-reproduced.json
```

0.7.13已接入四端手柄只读查询，见 [APP_HANDLE_SETTINGS.md](../../docs/APP_HANDLE_SETTINGS.md)。其余动作继续完成SDK、错误/超时/取消/互斥与编码测试，再在用户返回后的受控会话核对实际固件、效果、恢复范围与持久化。全部命令和本机验收仍未完成，两个完整性门槛保持false。



0.7.14微调请求契约与暂停标志/回调审计见 [APP_FINE_TUNE.md](../../docs/APP_FINE_TUNE.md)，工具现固定49方法，真实效果仍未验收。


## 手柄写入调用及失败回退审计（运行时仍0.7.14/原生0.3.14）

固定源码控制审计现66方法。HG724继承的三个手柄setter均新建DataGimbalSetHandleParams对象，仅设置一个字段：ControllerMode→dualChannelMode/0，PitchOrRollInverse→tiltDirection/1，YawInverse→panDirection/2。模式通过ControllerMode.value传递枚举值（含UNKNOWN255）；反向参数是布尔0/1。不能从PitchOrRoll的名字扩展出独立Roll开关。未指定字段沿新对象默认FF编码，固件是否保留仍未证实；不以读值重写所有8字段替代源语义。

对应写入成功回调仅报告null，不解码回读。失败回调没有直接上报原Ccode，而按ControllerMode/PitchInvertedControlEnabled/YawInvertedControlEnabled键调用DJISDKCache.getValue；这不是已证实的直接BLE读取。缓存取值回调Class.cast后使用if-ne比较对象引用，非Object.equals；非空结果中相同引用可回报成功，否则RESULT_FAILED；结果对象为空时直接返回、没有完成回调，取值失败则传递错误。不能复制为“写入失败也成功”，也不能据此声称固件写入接受或持久化。

读取ControllerMode的上层回调用values()[raw]数组下标，不是find(raw)；方向回调仅raw==1为true，不是bit0（raw3不等于true）。SDK现有getHandleSettings继续保留原值，不照搬源代码对异常值的数组风险，也不重解释既有结果。新增3项审计测试覆盖单字段新对象、禁止singleton/多字段/未构造、引用比较与错误分支变更。没有新增SDK发送、厂商代码执行或硬件操作；手柄写入SDK及本机验收仍待完成，两个完整性门槛false。
