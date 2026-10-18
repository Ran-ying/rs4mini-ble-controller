# BLE 直连服务与通用包管理器路由

2026-10-18，接续[校准传输审计](CALIBRATION_TRANSPORT.md)。固定官方APK与六个已恢复DEX的哈希，只读分析，不执行Android、Java/JNI、实时UI或硬件。

## 接收路径已定位

BluetoothService构造取DJIPackManager.getInstance()，该工厂创建名称Main的DJIPackManager；类直接继承DJIPackManagerBase，没有覆盖parse。BluetoothService.start把自身注册为BleManager的数据监听，BleManager委托BleConnector保存监听。

```text
BleConnector.onCharacteristicChanged → characteristic.getValue()
→ mDataListener.onDataReceived → BluetoothService.onDataReceived
→ DJIPackManager.parse（继承基类，offset0/完整数组长度）
→ SimpleComsumer队列 → DJIPackManagerBase$2.invoke
→ parseOne → 通用解密分类/包分发
```

基类构造needCheckEncrypt=true；Main子类构造enabledSetDataEvent=true。基类与DataBase从同一DJIEncryManager单例取策略。因此BLE源路径确实可以进入上一轮确认的SIMPLE分类和会话状态更新，不能因为没有“BlePackManager”类名便推断使用另一套协议。

这是构造完成后的静态源策略，不是对当前稳定器会话、Android运行调度或加密启用状态的测量。oldFirmware初始true和后续收包变化仍须分开；其他链路也可共享单例，不能将其当作独立的BLE连接状态。

## 链路选择与发送路径

BluetoothService.onConnect请求setLinkType(BLE)。DJILinkDaemonService先存linkType，再检查isAlive；未alive时不会继续切服务。alive分支的synthetic switch把BLE映射到case3，跳入BluetoothService.getInstance→changeTo；再调用ServiceManager.changeTo，将服务保存在mInterface。case3是switch值，不是链路枚举ordinal或线上字段。

```text
DataBase.submitTask → DataBaseProcessor.sendCmd
→ 常规Handler消息10 → realSendOnePack
→ ServiceManager.mInterface.sendmessage
→ BluetoothService.sendmessage → sendBuffer
→ 按getMaxDataLength分片 → BleManager.sendData
→ BleDataTransmitter.generateReq/队列/executeQueue
→ sendNonBlockingWriteRequest → BleConnector.sendData
→ characteristic.setValue → BluetoothGatt.writeCharacteristic
```

这里记录调用关系，不复制厂商调度、重发或超时策略进SDK。连接判断与BlockUtils升级过滤可能拦截发送；入队/调用写方法不等于设备接受或执行。sendBuffer读取已打包的buffer；通用包层的条件加密发生在它之前，不把它误作蓝牙服务另建一份明文业务包。

## 策略字段写入范围

六段可读恢复代码直接iput-boolean扫描得到五个构造方法：

| 构造来源 | 字段 | 写入 |
|---|---|---|
| DJIPackManagerBase | needCheckEncrypt | true |
| DJIPackManager | enabledSetDataEvent | true |
| DJINotSyncPackManager | enabledSetDataEvent | true |
| DJIArPackManager | needCheckEncrypt | false |
| DJIFlightLogPackManager | needCheckEncrypt | false |

后两类不同管理器的false不能搬给BLE所用Main管理器。没有发现其他直接字段写入，并不排除未恢复01/07、反射或JNI写入。寄存器字面量工具在分支和未知写入时丢弃旧值，无法解析就拒绝，不猜布尔值。

## 复现和下一步

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_ble_route.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/code-banks \
  --output work/research/ronin-ble-route.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_ble_route.py -v
```

[证据JSON](../../protocol/research/ronin-ble-route-evidence.json)保存37方法指纹、5处字段写入、明确路由及剩余边界，不含厂商完整指令。检查器验证固定输入、关键引用和已审阅的分支位置；不是完整控制流证明，也不模拟Android线程或实际通信。

上一轮“BLE管理器选择/开关源码尚未定位”现已补齐；实际会话策略和对端接受仍未知。下一步核对04:08的混合命令ACK分发、包层返回码和两字节业务状态之间的边界，再封装来源明确的候选请求；不需要因缺实机而重复研究已经确认的构造默认值。

运行时保持SDK0.7.29/原生0.3.29；没有新增发送、解密、相机/视觉或高级功能。全命令与高级开发门槛继续false。
