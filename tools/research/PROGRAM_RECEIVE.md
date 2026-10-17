# 程序接收：返回码、混合分派与扩展边界

2026-10-18，运行时/安装包仍0.7.21 / 原生0.3.21。
只读`ronin_program_receive.py`固定APK和六段恢复DEX，37个方法指纹、7个基础程序命令策略见
[证据](../../protocol/research/ronin-program-receive-evidence.json)。没有执行厂商代码、反射、网络/蓝牙或SDK。

## 基础命令表的实际策略

CmdIdGimbal继承DJICmdSetBase，getCurCmdIdValues返回CmdIdType.values；基础构造器按value()将条目写入SparseArray。
不是用ordinal作为wire编号。isBlock/isMix/isNeedCcode/getDataBase等查询通过该表的CmdIdInterface实现。
所选基础Gimbal枚举的isNeedCcode直接返回true。

| wire命令 | isBlock | isMix | 基础接收分派的可达路径 |
|---|---|---|---|
| 04:25、37、62、63 | true | false | 请求响应处理器；普通情况不进入推送对象 |
| 04:38、64 | false | false | 推送对象 |
| 04:6B | false | true | 请求响应处理器和推送对象两路 |

isBlock是这里的处理路径标志，不是“停止运动”。DJIPackManagerBase.setMsg先判断isBlock或isMix决定是否交给DataBaseProcessor，
随后根据isBlock及isBlePing等条件决定是否继续查找推送对象。表里描述的是路径资格，不代表后续查找、反射或处理器一定成功。
DataBaseProcessor内部序号/回调匹配尚未在本批审完。

04:6B基础条目关联DataGimbalGetPushExternalStatus，isMix=true。因此不能因“是状态通知类”就认定ACK只走请求回调，
也不能把推送事件直接当作某个本地请求已完成。38/64的isChanged会发送源ACK，这个行为与6B混合分派分开记录。

## 原始payload与业务体

RecvPack.setBuffer在frame offset11开始取payload。头部flags通过BytesUtil.getInt(B)转成0..255后再提取bit7命令类型。
当cmdType=ACK且命令策略需要ccode时，把offset11单字节取作ccode，业务data从offset12开始；
请求型包不进行这一步剥离。只在计算出的data长度>0时赋值data，不能从空业务体虚构新状态。
该setBuffer方法负责取字段，本身不等于整条链的CRC、长度、解密与端点验证。

对所选基础表程序命令：

- 请求型通知的业务offset0，对应原始payload offset0。
- ACK业务offset0，对应原始payload offset1；外层ccode与业务成功标志是两个字段。
- 例如原始ACK payload `00 01 62 04 01 02 03 04`，外层ccode=0，业务体从`01 62...`开始。
  业务解析器还会把首字节0或1均视为源success，不能合并为一个返回码。

`source_payload_view`要求显式needs_ccode上下文、仅解释未加密字节，保留raw/body两个视图，不构造DUML帧。
它是无状态的离线核对，不模拟RecvPack池化、重复使用或旧data生命周期，也不把NACK后剩余字节抹掉。
当前SDK的收发策略没有因这份研究改变；目标固件实际帧与扩展命令表选择仍未验证。

## 业务对象与事件顺序

DataBase.setPushRecPack将Pack.data交给setPushRecData；基础setRecData仅保存数组引用。
按senderId保存的recDatas也保存同一数组引用，不是深拷贝快照。

DataGimbalGetPushExternalStatus.setPushRecData首先invoke-super，随后才解析success和程序字段。
父方法在数据变化、isWantPush、isRegist等条件满足时调用post；post还检查ServiceManager.isAlive后发布EventBus对象。
所以源调用顺序允许“发布动作发生在派生字段解析之前”。具体订阅者是否异步、何时读字段，本批没有验证，不能直接宣称一定竞态。
未来SDK应按收到的单帧完成解析后发布独立快照，不复制源单例引用/保留字段为本次完成状态。

## 命令表扩展不能忽略

CmdSet构造器会先尝试getExtraCmdSetInterface；它用基础实例类名拼接
`com.dji.midware.extension.config.CmdIdGimbalExtra`并Class.forName/newInstance，成功时可替换基础命令表，失败返回null后保留基础表。
研究工具只读取这些指令，不执行Class.forName或构造器。
六段恢复DEX的该扩展命名空间定义匹配数为0，但银行1/7、未恢复/动态代码仍未覆盖，不能据此证明整个App无扩展。
因此本批建立的是基础路径的payload映射和分派证据，actualCmdSetExtensionSelectionVerified与设备验证均false。
不能把这个限定删除后宣称全App或RS4Mini协议已完全确定。

## 复现与剩余工作

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_program_receive.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/code-banks \
  --output work/research/ronin-program-receive-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_program_receive.py -v
```

哈希先校验再加载可选解析器。离线向量覆盖ACK/业务成功分离、无ccode上下文、空体、未加密限制、
混合/普通/阻塞及BLE ping分派条件、构造器三种布局和非wire哨兵拒绝。
仍需实际扩展选择、完整解密/帧验证、处理器匹配、程序单位/参考系、型号与实机执行/停止证据。
本批不新增SDK接收映射、查询/写入允许列表、相机或高级功能，全命令门槛false。
