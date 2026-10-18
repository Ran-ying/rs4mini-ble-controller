# 04:08与04:30校准域及近似类绑定

固定Ronin2.2.2/7096 APK与六段恢复代码，48个方法指纹、17个直接调用方法、9个类型化方法声明和9个外部枚举引用方法。证据为 `protocol/research/ronin-sensor-calibration-evidence.json`。工具仅离线读取，未执行厂商代码/线程/UI或操作设备，不提供SDK接口。

## 命令表先于类名

| 基础表命令 | 绑定的源类 | isBlock / isMix |
|---|---|---|
| 04:08 AutoCalibration | DataGimbalAutoCalibration | false / true |
| 04:30 GetPushSensorCalibrationStatus | DataGimbalGetPushSensorCalibrateStatus | false / false |

另一个DataGimbalGetPushAutoCalibrationStatus类不在本基础表04:30的绑定位置。它确实有progress/status两个整数getter，progress可带senderId varargs，isChanged总为true；这些不能套给实际绑定的SensorCalibrateStatus。实际30类继承父层变化检测，start(callback)只有return-void，不提供源查询动作。基础表仍不证明实际扩展表/固件选择。

## 04:08请求与响应

源构造器默认部件AUTO；setCalType设置部件，doPack分配1字节并写显式enum value。10个值0..9依次为AUTO、JOINT_ANGLE、HALL_LINEAR、JOINT_ANGLE_CAMERA、JOINT_ANGLE_FIXTURE、GYRO、ACCELERATION、COMPASS、IMU_AND_SENSOR、SHOCK_PLATE。枚举构造实值已核对，不能据ordinal泛化。研究保留完整目录，不因此提供相机或任何校准控制。

start设置APP→GIMBAL、REQUEST、ACK.YES、未加密、04:08，并赋getSendData到SendPack.data。该方法不显式写receiverId；基类业务调用中另有setReceiverId，实际完整路由仍需审计，不能断言固定本机索引。

源响应getType读取业务偏移0/宽1，未知回退AUTO；getStatus读取偏移1/宽1，FAIL=0、SUCCESS=1、PROCESSING=2，未知或短/空状态回退PROCESSING。回退值不证明设备仍在校准。基础GIMBAL表的ACK外层ccode按既有包层剥离后，业务偏移才成立，不能把返回码当part或状态；非零返回码与业务SUCCESS也不能合并成成功。

离线auto_calibration_response_body只接受完整两字节业务体，保留rawPart/rawStatus、源回退名及known标志、尾字节，不模拟缺数据时的虚构PROCESSING。source_start_body只是单字节离线核对，不构造DUML或被SDK引用。

## 04:30传感器校准推送

实际SensorCalibrateStatus的getProgress读取业务偏移0/宽1，getStatus读取偏移1/宽1后经自身CalibrationStatus.find映射：

| 原始状态 | 源枚举名 | enum ordinal |
|---|---|---|
| 0 | COMPLETE | 0 |
| 1 | PROCESSING | 1 |
| 3 | FAIL | 2 |
| 9 | OTHER | 3 |

2不是FAIL，未知值回退OTHER但必须保留raw；1在08响应是SUCCESS，在30推送是PROCESSING，0亦分别是FAIL与COMPLETE。不能把30的非零状态统一转换成inProgress=true。

短/空数据的源progress返回0、状态OTHER。离线sensor_progress_body严格要求完整两字节，不复制这个缺失值补零行为；保留完整0..255进度原值与尾字节，不截断到100。状态与进度来源字段均不证明物理完成，未确认进度单位或本机布局。

既有SDK的other-model实验配置保留原格式；本研究不把新App布局偷偷套到该配置，也未增加当前App来源的30接收或08发送。

## 业务调用与其他校准域

17个直接调用包含ConfigMotorBasicView/其RoninSc版本的correctJointAngle、SettingGeneralView/SettingMoreView的startCalibration、ConfigNewSettingsView的startCalibration/startAdvancedCalibration与两种事件回调，以及DJIGimbalAbstraction的startCalibration。近似AutoCalibrationStatus还被若干飞行器抽象读取。调用/类型化声明目录只列直接静态引用，不等于HG724可达入口或实际执行。

ConfigNewSettingsView分别处理08响应与30推送，引用各自独立状态枚举。型号/UI挂载条件、程序关联及完整流程仍待逐项追踪；没有据继承或界面类名宣布RS4Mini支持。

以下域保持分开：system_calc/index36的0F/10与DEFAULT/START/FAIL/SUCCESS；balance_test/index37；6A/6E电机自动调参；08部件校准请求/响应；30自身状态推送。水平校准身份、终止/恢复、真实路由和物理效果仍未证明。

## 复现与验证

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_sensor_calibration.py --apk work/research/dji-ronin-2.2.2.apk --bank-dir work/research/code-banks --output work/research/ronin-sensor-calibration.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_sensor_calibration.py -v
```

APK与所有六段哈希在导入可选DEX解析器前校验。12项新增测试覆盖10部件、两种状态域、全部字节值/未知回退、尾字节/快照、外层ccode与业务状态分离、短体拒绝、逐段哈希先验和正确类绑定。运行时仍0.7.27/0.3.27，无SDK收发扩展、相机/视觉/高级功能、硬件/liveUI/厂商执行；完整命令和高级门槛false。

最终固定输入独立提取两次，完整证据JSON逐字节一致。Python3.8与3.12完整研究工具各342项通过；统一离线Node235/Web22/Python211/原生356+240+3及类型、边界、构建通过。
