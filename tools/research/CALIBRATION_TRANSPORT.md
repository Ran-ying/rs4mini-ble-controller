# 校准请求默认包头与条件加密

2026-10-18，接续[校准入口](CALIBRATION_ENTRY.md)和[角度包上下文](ANGLE_CONTEXT.md)。固定 APK 与六段恢复 DEX；只读取元数据及指令，不执行 APK、Java/JNI、实时 UI 或硬件。

## 默认地址与标志

新建 DataGimbalAutoCalibration 直接继承 DataBase。DataBase 构造的 receiverID/senderID 是−1；SendPack→Pack 构造没有赋值 senderId/receiverId，Java int 默认0。校准自身没有 setReceiverId。接收类型GIMBAL=4，因此这个新对象、未额外覆写的源分支地址字节为04，发送类型APP=2、ID0对应02。

校准 start 设置 REQUEST=0、NEEDACK.YES=2、Encrypt.NO=0。YES的ordinal不是线上数值；SendPack按(cmdType<<7)|(isNeedAck<<5)|encryptType打包，所以条件加密前flags为40十六进制。校准体和响应仍见[SENSOR_CALIBRATION.md](SENSOR_CALIBRATION.md)，不把包层返回码当作校准业务状态。

有回调start委托三参数重载；三参数start和无回调preprocessPack都会在receiverID !=−1时覆盖SendPack.receiverId，再getSendData/doPack。以上是新对象静态路径，不能推出任何既有实例、其他通道或本机地址。

## 通用发送层可改写加密

DJIEncryManager初始isOldFirmware=true。它是可变会话布尔量，不是读取的固件年代、型号或能力。两个发送入口在该量false且isNeedEncrypt为true时，调用simpleEncrypt，以SIMPLE=3修改flags并重新CRC。业务类Encrypt.NO不能单独证明最终线上为明文。

固定源isNeedEncrypt读取包字节9/10：COMMON=0全部false；CAMERA=2的命令16/17/112/113为false；其余为true。GIMBAL=4的所有命令，包括04:08，均落true。CAMERA不是1；SPECIAL=1不能与它混淆。

## 接收端改变会话策略的真实分支

六个已恢复银行中，setIsOldFirmware的直接调用者仅DJIPackManagerBase.parseOne一处方法、两次调用。段01/07未恢复，反射/间接及动态路径不在直接扫描保证内。

- needCheckEncrypt=false：跳过这段策略，保留原状态。
- needCheckEncrypt=true且enabledSetDataEvent=true，低三位恰为3：设置oldFirmware=false，取字节6..7作为参数调用simpleDecrypt。
- 否则进入isNeedEncrypt判断；判断true时设置oldFirmware=true。**enabledSetDataEvent=false仍会走这个判断**，不能把两个布尔量误写成整个策略的共同门槛。

这里的isNeedEncrypt输入是当时包字节；若它们仍为密文，不能把离线传入的命令号当成已解密命令号。检查工具只模拟明确输入的策略，不执行或模拟实际密码算法。

simpleEncrypt/simpleDecrypt均复制从offset9起的length−11字节给GroudStation.native_rcDataDeal，再复制回来；范围包括命令集和命令号，不只是业务payload。JNI算法没有实现或执行，不应把它猜成只加密payload的异或。

## 复现与边界

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_calibration_transport.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/code-banks \
  --output work/research/ronin-calibration-transport.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_calibration_transport.py -v
```

[证据JSON](../../protocol/research/ronin-calibration-transport-evidence.json)记录28方法指纹、实际枚举值和直接调用范围，不含厂商完整代码。工具验证固定输入哈希、选定CmdSet在线性前缀中的构造值、关键分支目标及人工审阅的parseOne指纹；不是通用控制流解释器或全App可达性证明。

仍缺直连BLE实际manager的开关配置和消息路径、真实会话状态与对端接受证据、JNI算法以及物理完成/中止。下一步应追踪manager选择与开关写入，不需要重复猜测业务体或默认地址。SDK仍0.7.29/原生0.3.29，不开放04:08、不改变发送允许列表或完整性门槛。
