# 04:69外设数据源审计

固定Ronin2.2.2/7096 APK及六段恢复代码，只读审计36个方法、完整DataType/SpeedControlType构造实值及外部直接调用。证据为 `protocol/research/ronin-external-device-evidence.json`。不执行厂商代码，不提供SDK收发，不实现相机或视觉跟踪。

## 接收业务体

源setPushRecData先调用DataBase父层，再从业务体偏移0读取TLV：tag与length均由aget-byte读取，因此高位字节有符号。每条记录结束为原offset+2+源length。仅SpeedControl/tag2被此类解析，其余类型在本类没有字段解码。

| 相对SpeedControl载荷偏移 | 源读取 |
|---|---|
| 0 | 控制来源，最终&255 |
| 1..2 | Pitch原始有符号16位LE |
| 3..4 | Roll原始有符号16位LE |
| 5..6 | Yaw原始有符号16位LE |

来源枚举为CommonStick=1、RockWheel=2、Sensor=3、Other=7。未知值经find回退Other；必须同时保留原值，不能把Unknown变成确定的7。它与DataType.Other=255不同，ordinal也不是wire ID。

源convertTwoSignInt将高字节左移8位，低字节&255后按位或，得到signed16值。未定位物理单位、比例或与04:05姿态/机械关节的关系，不据Speed命名声明角速度。源getter直接读单例字段；一帧缺少SpeedControl时保留旧字段，多条SpeedControl依次覆盖，null或长度<=1只清三轴速度而保留控制来源。

研究工具external_body只产生当前完整帧视图，保留全部未知/重复记录与额外字节。拒绝负length、截断头/体和不足7字节的SpeedControl，不复刻源无完整验长的异常/循环或旧缓存副作用。未知记录不合成速度，不能把本工具当作源单例模拟器或SDK接口。

## 发送及基础分发

源start设置APP→GIMBAL、REQUEST、NEEDACK.NO、未加密、04:69；字段repeatTimes=2/timeOut=1000不证明真实重发策略。方法不显式写receiverId。doPack只有return-void，不赋_sendData；这不足以宣称实际链路发送了空业务体，尚未审计其完整运输上下文。

基础命令表isBlock=false/isMix=true，因此按既有基础包层可同时满足处理器与推送路径条件；基础GIMBAL表的ACK需ccode策略与此源发送不请求ACK是两个不同事实。当前App实际扩展表选择、本机路由和真实通知均未证实。见[基础接收路径](PROGRAM_RECEIVE.md)。

## 调用与范围

六段唯一枚举外直接调用方法为business03的TrackingPresenter.runGimbalJniCtr，读取getInstance/getYawSpeed/getPitchSpeed；没有找到外部直接调用此类start或getRollSpeed/getSpeedControlType。枚举外类型化参数/返回值声明检索为0。这些都是限定范围的检索结果，不排除事件总线、反射、JNI、未恢复1/7段和其他类加载器，也不证明功能不受支持。

跟踪界面中的消费不是HG724命令支持证据。本次不继续实现相机/视觉产品功能，也不据这个类名开放设备查询或控制；只补齐底层命令研究。

## 复现与未完成项

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_external_device.py --apk work/research/dji-ronin-2.2.2.apk --bank-dir work/research/code-banks --output work/research/ronin-external-device.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_external_device.py -v
```

输入APK和全部六段哈希在导入可选DEX解析器前校验。11项测试覆盖符号端点/轴序、源枚举实值与未知、重复/尾字节、未知帧不造旧值、坏TLV、127/128长度边界、快照、枚举ordinal区分、逐段哈希先验和证据边界。型号分支、单位、地址、运输body、实际扩展与本机通知仍未完成；运行时0.7.26/0.3.26不变，完整命令与高级开发门槛false。

最终工具从固定输入独立提取两次，完整证据JSON逐字节一致。Python3.8与3.12完整研究工具各330项通过；统一离线Node229/Web21/Python205/原生324+233+3及类型、分层、构建检查通过，运行时未改动。
