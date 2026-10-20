# 回中：通用SDK平台分支与App直接入口

2026-10-17，固定六段恢复视图，27方法指纹/8个直接调用方法见
[证据](../../protocol/research/ronin-reset-routes.json)。运行时保持0.7.19 / 原生0.3.19。
没有新增SDK发送、相机/飞行功能、硬件/liveUI/厂商执行或高级组合。

## 通用resetGimbal不是统一的04:4C流程

HG724继承链中的基础resetGimbal先调用暂停等待；失败直接返回。
随后用DJIComponentManager.PlatformType比较M200、M210、M210RTK：

| 源平台比较 | 选中的通用路径 |
|---|---|
| 三个名字之一 | 新建DataGimbalNewResetAndSetMode，setReset(true)，回调start |
| 其他名字 | DataSpecialControl.getInstance().resetGimbal().start(20)，立即onSuccess(null) |

code-unit跳转：4→99是暂停失败返回；20/28→69是前两种匹配；36→39为第三种不匹配，
38→69为第三种匹配。不能把goto位移当字节偏移，不能把源platform与GimbalComponentType
或App类型枚举103混用。若源PlatformType名字为HG724，会落入第二行；这只是条件判断，
没有读取本机平台字段、验证App实际调用入口或证明固件兼容性。

第二行还包含独立的产品选择：DataSpecialControl.useNewControl读取DJIProductManager.ProductType，
Pomato/Orange2/M200/M210/M210RTK/Potato选DataNewSpecialControl，其余选DataOldSpecialControl。
PlatformType、ProductType与HG724云台型号是三个来源，不能用“HG724继承该类”推定产品选择结果。
传给start的20也不是角度到位时限；旧实现非零值走Handler，源码还安排100ms消息，完整调度未审完。

## SpecialControl不是安全的替代回中包

新旧实现使用SPECIAL命令集，Control=1、NewControl=3，不是GIMBAL/04命令。
它们的业务体混有其他子系统字段；本批只追踪回中相关路径，不新增相机、飞行或通用任意写入。

旧doPack为10字节，包含mCameraByte、回放、mGimbalByte、飞行模式等字段和异或尾字节。
resetGimbal先_reset，再置mReceiveType=GIMBAL、mGimbalByte=1；但_reset没有写mFlycMode，
不能擅自假定其他字段全部清零。sendPack还按产品/链路选择receiverType，设置receiverId5，
随后DataBase仍可能应用存储receiverID覆盖。不能因resetGimbal里出现GIMBAL就说线上最终发给04。
新实现有doCommonPack等子结构，本批未完成整个混合体审计，均未开放发送。

## App直接回中入口补齐

六段扫描找到DataGimbalNewResetAndSetMode的8个直接调用方法：bank0左栏一个，bank3 Ronin UI四个，
bank5基础reset/setGimbalMode两个及DT501 UVC一个。UVC仍在排除范围，不实现相关接口。

本批进一步核对三个bank3入口：CreateUtils.recenterGimbal、RoninBackInTextView$1.onClick、
SettingRoninsGeneralView.onClick的相应分支。它们直接构造该类、设MODE.OTHER与reset=true并调用回调start，
没有在所选方法中调用通用resetGimbal或两个stabilization辅助方法。

创建工具/回中控件先检查连接及MotorEnabled缓存；控件还有1000ms点击间隔。
设置页检查连接/remote，手持设备分支检查电机缓存；这些是源UI条件，不是已验证的BLE电机读数。
不擅自将UI缓存检查接成SDK隐式写入或把缓存false解释成设备故障。
所选入口没有HG724专属条件证据；其实际挂载/可见性未完全审计，不能说完整型号UI路径已经验证。

DataGimbalNewResetAndSetMode构造默认mode=OTHER、reset=false；doPack两字节是mode.value低字节和布尔0/1。
源MODE：YawNoFollow=0、FPV=1、YawFollow=2、OTHER=254。
所以这些UI分支的源体为FE01，与历史RS4Mini回中体一致。匹配字节加强来源解释，
仍不证明整套通用SDK工作流、本机ACK/到位/取消或其他模式兼容。
0/1/2不能直接当PF/PTF/FPV完整预设、参数62工作模式或按轴回中枚举。
FE00仅为纯离线编码例，不宣称有设备释放/停止效果。

现有SDK固定FE01三轴回中保持不变；没有新增SpecialControl发送、单轴回中或模式切换接口。

## 复现与余项

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_reset_routes.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/code-banks \
  --output work/research/ronin-reset-routes-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_reset_routes.py -v
```

工具先验证全部哈希，仅做指纹、引用、固定分支及常量核对；不是通用CFG/虚拟机，语义来自固定方法人工静态核对。
手写帮助函数仅做条件比较与两字节编码，无DUML、SDK导入、蓝牙发送或厂商执行。
未恢复banks1/7、残留保护桩/动态路径不在完整覆盖内，零引用不能判不支持。

继续审计实际HG724动作注册/入口、模式调用与响应、地址和物理完成/取消；全部命令与高级新增门槛仍false。

## 后续：八段运动重审（2026-10-20）

见 [MOTION_PREFIX.md](MOTION_PREFIX.md)。
