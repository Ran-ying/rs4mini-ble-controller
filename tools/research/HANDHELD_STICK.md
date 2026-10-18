# 04:57/58 手柄状态与控制候选

2026-10-17，固定APK与六段恢复视图，23方法指纹和2个类外直接调用方法见
[证据](../../protocol/research/ronin-stick-evidence.json)。未执行厂商代码或操作硬件。

DataGimbalGetPushHandheldStickState继承DataBase，不覆盖get/setPushRecPack/setPushRecData/setRecData。
枚举GetPushHandheldStickState的wire值87（0x57），ordinal39不是命令值，绑定该类。
源业务get使用Short与shortValue；DataBase.get的Short分支调用BytesUtil.getShort，后者按LITTLE_ENDIAN读short。

| 源getter | 业务偏移/宽度 | 源解释 |
|---|---|---|
| getStickX | 0/2 | signed int16 LE |
| getStickY | 2/2 | signed int16 LE |
| isTriggerPressed | 4/2 | word &1 ==1 |
| isStickGimbalControlEnabled | 4/2 | word &2 ==2 |

最少6字节；两个bool读取同一个short，符号位不会改变低位测试。SDK保留uint16的rawStateWord和其余位，
不归一化摇杆、不假定中心值、单位、坐标系或Pan/Tilt映射。只对未加密请求型消息应用源业务布局，
与现有固定推送一样经过RecvPack请求体→DataBase原始_recData路径；ACK不能照用偏移。
这是源包层证据，不是本机布局验收；短消息不补零。

DataGimbalSetHandheldStickControlEnabled构造默认false，setter直接存bool；doPack一字节0/1。
start为APP→GIMBAL、GIMBAL命令集、SetHandheldStickControlEnabled=88（0x58）、请求ACK。
只读研究帮助函数可复现00/01，不构造DUML，不向设备发送。

六段类外直接调用只见bank05 MobileHandheldControllerAbstraction：状态事件和一个setter。
setter源码方法名是setIsInternalAndExternalMicroPhonesEnabled，却调用该58类；不能据方法名认定麦克风能力，
也不据类名认定HG724手柄支持。记录的是固定方法指纹及引用，不诊断厂商bug或改变范围。
没有HG724专属绑定、真实58接受/效果或持久化证据，因此没有增加58发送。
未恢复banks1/7、保护桩与动态路径仍未排除，零引用不能判设备不支持。

0.7.20仅在显式ronin-2.2.2配置下新增57被动候选，四端接口/未验收项见
[SDK说明](../../docs/APP_HANDHELD_STICK.md)。不增加订阅、查询、轮询、按键映射或高级动作。

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_stick_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/code-banks \
  --output work/research/ronin-stick-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_stick_trace.py -v
```

工具先检查所有固定哈希，输出指纹/字段与直接引用；Short getter前缀拒绝未知分支/类型/宽度。
其余关键方法按固定指纹人工核对，工具不是通用CFG或虚拟机，不保存厂商反汇编。
全部命令完整性及新增高级功能条件仍false。


后续[HG724工厂与Setter绑定](HANDHELD_BINDING.md)补齐明确HG724平台条件下的Mobile选择及实际StickGimbalControlEnabled注解；本页“尚无型号源绑定”为当时状态。仍未提供58发送或实机效果/持久化证明。
