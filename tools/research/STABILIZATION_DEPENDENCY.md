# 角度/回中源码的 stabilization 依赖

2026-10-17。接续[角度上下文](ANGLE_CONTEXT.md)，只为审计底层角度、微调与回中源路径。
不新增相机/视觉功能，不把 EYE 状态当稳定器运动状态；无 SDK 发送、硬件/liveUI 或厂商代码执行。
运行时保持0.7.19 / 原生0.3.19。固定六段、16方法指纹与6个直接调用方法见
[证据](../../protocol/research/ronin-stabilization-evidence.json)。

## 状态字节：源业务体，不是已确认本机 BLE 偏移

DataEyeGetPushStabilizationState 的三个getter从业务偏移0、宽1读取：

| 源值 | 含义 |
|---|---|
| bit7 | getStateIsTurnOn |
| bit6 | 开启时，1表示getStateIsPaused=false，0表示true |
| 低6位 | getPauseReason输入值，非电机角度或到位状态 |
| 未开启 | getStateIsPaused直接返回true，不再用bit6 |

因此任意0..191源值的paused均为true，192..255为false；needPause是turnedOn且notPaused，
即源值192..255。这里的“关闭也算paused”是源getter策略，不表示固件已接受暂停请求或云台停止。
不把bit6直接当paused标志，不在没有本机来源证据时将该字节接入现有反馈。

源原因枚举：UnCharacteristic0、CameraChanging1、GimbalMoving2、DroneMoving3、Tracking4、OTHER255。
掩码后只可能0..63；OTHER255是find的兜底枚举，不能说线上低6位能直接传255，未知原值应保留。
EYE枚举把GetPushStabilizationState关联到该类，wire值97（0x61），ordinal34不是命令值。
这是EYE候选，不是04:61，也没有确认此通知在本机直连BLE出现。

## 两种源流程不同

rotate的角度与速度分支调用justSendPauseData：发无回调EYE/AppState START后继续，不等状态或ACK。

tryToPauseTheStabilizationIfNecessary的静态路径为：

1. needPause=true：创建CountDownLatch(1)，加入waitList，发送同一无回调START，最多await 3秒。
2. 状态事件若开启且未暂停，仅置needPause=true并返回；关闭或已暂停时置false，遍历所有waitList并countDown。
3. 正常/中断路径在等待结束后移除本次latch。正常超时置失败标志；有callback时报告CANNOT_PAUSE_STABILIZATION，返回false。
4. needPause=false也发送START，不是无操作，未建立它是恢复请求的证据；返回true。

状态事件没有请求序号、目标角度、动作ID或端点校验。任何满足条件的源状态事件都可释放该列表等待者，
没有证据可以用它表示某个原生角度命令完成。请求ACK与状态等待也是不同路径。

真实异常表覆盖code units16..38，InterruptedException跳到40；await位于34。
handler打印异常，随后移除latch；若await抛出中断、尚未写入结果，初始失败标志仍为false，
源路径可能返回true而没有收到paused事件。这里记录固定方法行为，不照搬为SDK取消成功或物理暂停成功。
工具核对该选定异常表及分支锚点，不声称完整通用CFG或所有异常已分析。

## 调用与型号边界

六段扫描找到6个直接调用方法，全部在bank05：基础云台类状态事件、resetGimbal、rotate，
以及IntelligentFlightAssistant1860的三个状态同步/处理方法。负面检索不排除banks1/7、保护桩、动态路径。
飞行辅助名称及DroneMoving枚举进一步要求区分通用库与目标设备，不能据其存在宣布RS4Mini支持。
没有新增飞行、相机或视觉接口。

HG724继承链只有基础类定义resetGimbal，该方法先调用等待函数，然后按平台分支使用
DataSpecialControl或DataGimbalNewResetAndSetMode。该平台分支本批尚未完整审计，
不能把继承方法名当HG724实际包体或用它替换已实测FE01。现有回中实现保持不变。
Roll微调另检查needPause主机字段并可失败，没有自动调用等待函数，沿用既有文档边界。

所选rotate/等待函数都只见START，未建立恢复协议；这不是全App没有恢复的证明。
也未建立原生角度到位、取消或释放能力。现有stop仍是主机三帧中位，不能承诺原生程序中止。

## 复现

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_stabilization_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/code-banks \
  --output work/research/ronin-stabilization-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_stabilization_trace.py -v
```

工具先校验全部输入哈希，再加载可选解析器，只保存指纹/事实/调用分类，不保存厂商反汇编。
手写函数仅解释单个源业务字节，不构造DUML、不引用SDK、不发送或订阅。
新增检查覆盖全部256源值、关闭语义、无效输入、code-unit跳转、等待常量/结果反转变更和哈希预检。
下一步可继续审计reset平台分支、直连入口与其余命令；完整命令和高级新增门槛仍false。
