# 外设状态完整源目录与接收条件

2026-10-18，固定APK/bank05的70方法指纹，46个DataType、43个数值/布尔getter视图。工具ronin_peripheral_trace.py不导入SDK、不构造DUML帧、不执行厂商代码。
证据见protocol/research/ronin-peripheral-evidence.json（仓库根目录）。源码目录覆盖不等于本机字段或全协议已验证。

## 不能修正的源异常

YGyroOut和PAcceOut都用mId21，分别float32除10、除100；不能猜PAcceOut应为缺号22。SDK同时保留sourceTypes和两种带来源的sourceViews，ambiguous=true，不选一种当本机含义。
GpsLat/GpsLong的getter先signed int除1000000，再转double；-2999999返回-2.0，不擅自改成浮点除法或推断本机具备GPS。
getPMotorCurrent/getRMotorCurrent/getYMototBattery三个方法仅return-void；名字不改，不能给三项电流编造getter。PMotorCurrent/RMotorCurrent/YMotorCurrent标签保留原始体和类型名，但没有数值视图；Other也无getter。
完整字段与getter对应关系保存在证据catalog，DataType ordinal与mId分开。

## 整数全宽度与记录

getIntValue：长度1为signed byte、2为signed short LE、8为signed long LE再intValue窄化；其他长度走Integer，fillBytes尾部补零到4字节，超过4只读前4字节。arrayComb已核对先第一个数组再第二个，非前补零。
因此长度0的实际空记录产生源值0；长度3的ff ff ff得到16777215；长度>=4读取低32位并作signed int，包括8字节高位被丢弃。所有可用源signed长度0..127均有离线核对。
缺失记录与实际存在的空记录分开：不为没有出现的标签补0。float getter先int→float32再除10或100并float32舍入；bool视图为ControlState低两位等于2。

setPushRecData先调DataBase再解析，首字节1选择记录分支，tag/length来自signed byte；源map不清旧字段且缺值getter返回0，父层可能在派生解析前发事件。独立分析视图只表示当前完整帧，保留重复/未知记录，不复制旧map、缺省零或未验长读取。
原始tag>=128转成负map键，不能按正255自动命名成Other。负长度高位拒绝，截断拒绝整帧。

## 包层

基础枚举04:66是isBlock=false/isMix=false的纯推送，模型DataGimbalSetPushPeripheralStatus直接继承DataBase，无setPushRecPack/setRecData/isChanged覆盖。
结合已审计RecvPack/DataBase路径，请求型业务体从payload[0]开始；ACK根据needCcode剥离外层返回码，SDK本候选入口直接拒绝ACK。其源记录flag1不是外层ACK成功码。
该结论限基础表/所选类。CmdSet仍可能选择动态Extra，未证明运行时实际选择、本机端点/布局或固件支持，不宣称全部App/协议。
SDK候选合同见[APP_PERIPHERAL_STATUS.md](../../docs/APP_PERIPHERAL_STATUS.md)，没有新增订阅、自动ACK或控制。

## 复现

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_peripheral_trace.py --apk work/research/dji-ronin-2.2.2.apk --bank-dir work/research/code-banks --output work/research/ronin-peripheral-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_peripheral_trace.py -v
```

9项新增研究检查覆盖全宽度符号/补零/窄化、float/GPS顺序、未知/重复/缺失记录、getter精确寄存器/类型绑定、保护桩区别和哈希预检；六组黄金向量与三端共享。APK/DEX/完整反汇编不入Git。
