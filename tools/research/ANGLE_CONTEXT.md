# HG724 原生角度能力与包上下文

2026-10-17，接续[角度布局研究](ANGLES.md)。固定 APK/SDK 哈希与29方法指纹见
[证据](../../protocol/research/ronin-angle-context.json)。源码静态证据，不执行厂商代码或操作硬件。
没有新增 SDK 发送、相机/视觉功能或高级组合；运行时保持0.7.19 / 原生0.3.19。

## 能力覆盖顺序

HG724没有覆盖initGimbalCapability；HG702调用Ronin2→RoninBase→Handheld→X3→基础类，
父类先初始化，子类后覆盖。Aircraft无此方法定义。

| 来源层 | Pitch | Yaw | Roll |
|---|---|---|---|
| X3 | −90..30 | −180..180 | −15..15 |
| Handheld | −120..30 | −180..180 | supported=false，范围占位0..0 |
| RoninBase | −135..45 | −179..179 | 沿用 |
| Ronin2 | 沿用 | 沿用 | −30..30，supported=true |
| HG702/HG724继承结果 | −90..90 | −180..180 | −30..30 |

基础类先建立Map和默认能力；addIsSupportedToCapability为min/max类构造支持标志及0..0占位；
addMinMaxToCapability为min/max类构造supported=true与指定范围，再Map.put覆盖同名键。
不能停在Handheld的Roll=false便断言HG724不能控Roll。

工具按方法解析结果逆序合并源码声明；这是初始化后的源策略，未排除后续动态修改，
不是设备实时能力、机械限位、防碰撞范围或所有姿态下的运动许可。绝对角rotate使用这些源能力；
相对角分支的检查不同，不能把绝对角范围机械地加到现有机械关节moveTo或其他模型接口。

## 接收地址传递

基础getReceiverIdByIndex读取初始化时的index，调用DoubleCameraSupportUtil.getGimbalIdInProtocol：
源int index精确等于1时返回2，其他int返回0，包括负值；不是index非零就返回2。
DataBase.setReceiverId保存receiverID；无回调start走preprocessPack，有回调start转交三参数start；
两处均在存储receiverID不等于−1时覆盖SendPack.receiverId，再打包。
SendPack.doPack把receiverId左移5与receiverType OR进接收字节。

这补齐静态地址传递，不证明当前直连设备的index、线上地址或通用包层加密条件。
两个start包层均有加密管理分支，本批仅记录指纹/相关路径，不据协议类的Encrypt.NO
断言所有传输路径最终明文。没有修改SDK地址或加密行为。

## 所谓“暂停”实际上发送另一类消息

justSendPauseData新建DataSingleSendAppStateForStabilization，设GimbalState.START后调用无回调start。
构造默认gimbalState=NORMAL、cameraState=NORMAL；源枚举START=1、camera NORMAL=0，
本次调用的两字节源体因此为0100。这是源状态编码，不能从START名字解释成物理暂停保证。

| 项目 | 无回调start()：rotate实际调用 | start(callback)：不同重载 |
|---|---|---|
| 接收类型/ID | SINGLE，源类型值17，ID7 | 同类字段，不能改作GIMBAL |
| 命令集 | EYE | EYE |
| 源命令名/值 | AppState=98（0x62） | Stabilization=96（0x60） |
| 请求ACK | YES | YES，另有源timeOut1000/repeatTimes2 |

这些不是04:62/04:60；相同命令字节跨命令集不能合并。
无回调方法没有等待业务ACK再进入角度请求，不能把其上层成功当暂停成功。
没有确定direct BLE必须发送、该设备有SINGLE/id7组件、恢复步骤或实际效果。
不把带cameraState的通用消息扩展成相机接口，不把另一重载当作“暂停确认”。

## 复现与仍缺事项

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_angle_context.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --sdk work/research/code-banks/business-05-code-restored.dex \
  --output work/research/ronin-angle-context-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_angle_context.py -v
```

仅识别直线声明中的literal、Integer装箱、键和能力setter；拒绝条件分支，未知寄存器写入
丢弃旧值，包括wide相邻寄存器；它不是通用虚拟机或完整CFG/副作用分析。
指纹固定人工核对的包层方法，工具检查关键引用；不把范围合并当动态设备行为证明。

下一步需核对直连入口是否使用/裁剪EYE依赖、错误返回/完成/取消/释放，以及本机坐标与地址。
没有证据前不补一个擅自省略依赖的原生定位接口，也不宣称暂停请求已验收。
仍可继续离线研究其他命令；全部命令完整性与新增高级功能门槛保持false。


[暂停状态与等待依赖审计](STABILIZATION_DEPENDENCY.md)区分源stabilization状态、3秒等待与真实云台停止/到位；关闭也返回paused、等待不按请求序号关联，未新增运行时功能或声明本机支持。
