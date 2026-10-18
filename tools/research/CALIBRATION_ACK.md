# 04:08 ACK、业务状态和混合分发边界

2026-10-18，接续[BLE路由](BLE_ROUTE.md)、[校准传输](CALIBRATION_TRANSPORT.md)和[08/30校准域](SENSOR_CALIBRATION.md)。本批在固定APK/已恢复bank05上独立核对20方法；包层通用规则此前见[程序接收审计](PROGRAM_RECEIVE.md)，此处补齐04:08绑定、回调状态和源请求关联的具体边界。只读静态分析，不执行厂商代码、反射、Android线程或硬件。

## 线上偏移已明确

基础CmdIdGimbal表绑定AutoCalibration/04:08→DataGimbalAutoCalibration，isBlock=false、isMix=true、isNeedCcode=true。RecvPack按ACK位与表规则，读取原始payload首字节为无符号ccode，再把剩余部分放入业务data；请求型通知不剥离首字节。

| 字段 | 原始ACK payload偏移 | 业务data偏移 |
|---|---:|---:|
| 包层ccode | 0 | 不在业务体中 |
| 校准部件part | 1 | 0 |
| 校准状态status | 2 | 1 |

基础表ACK为`00 05 01`时，包层返回码0、部件GYRO=5、业务SUCCESS=1；`00 00 00`则是包层成功、部件AUTO、业务FAIL，不能合并成“校准成功”。请求型`05 01`的业务体就是`05 01`，不丢掉部件字节。条件加密报文不能直接走这个明文视图。

源RecvPack只有剩余业务长度大于0才赋data；研究视图始终使用本次输入的独立字节，不模拟池化对象历史状态。ACK只有返回码或仅一个业务字节时，标记businessComplete=false、calibration=null，保留原始体；不填补PROCESSING，不假造部件或进度。

## 回调成功不是业务SUCCESS

DataBase.sendPackResult保存RecvPack后提交DataBase$3。对需要ccode的GIMBAL，Ccode.OK线上值0才走成功回调；Ccode.SUCCEED=1的额外成功分支仅属于CAMERA，不能套用到GIMBAL。失败分支同样把业务data交给setRecData，但不会因此成为成功。

成功回调不检查DataGimbalAutoCalibration.getStatus。返回码0、完整业务体、业务SUCCESS1以及真实校准完成是四个不同条件。本研究不把任何一个提升为实际物理完成；不将NACK里的成功样字节缓存成正常状态。

## 混合命令与请求关联

isBlock=false/isMix=true允许进入DataBaseProcessor路径和push路径。源DataBaseProcessor.getKey只组合cmdSet<<24、cmdId<<16和seq；setMsg检查map键后投递Handler消息12。这个key不含ACK位和发送/接收地址，也不证明队列回调、成功或到位。

SDK应保留已有更严格的会话、ACK位、端点、命令和序号关联，不复制较弱的源key。混合命令通知或04:30传感器状态均不能随便完成04:08请求；各状态域继续分开。

## 复现与SDK接入条件

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_calibration_ack.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --sdk work/research/code-banks/business-05-code-restored.dex \
  --output work/research/ronin-calibration-ack.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_calibration_ack.py -v
```

[证据JSON](../../protocol/research/ronin-calibration-ack-evidence.json)包含方法指纹、条件基础表偏移、回调规则和未验证项，不包含厂商完整代码。工具检查固定输入、关键分支和精确的key指令形状；不是全控制流解释器或实际CmdSet反射选择证明。

至此，源码已明确的HG724高级AUTO00入口、默认包头、BLE路由及基础表ACK偏移可以支持继续设计显式来源的候选SDK封装。仍须明确MotorEnabled缓存门槛由谁提供，返回码/业务状态分别报告，取消只结束主机等待、不虚构固件中止，并保持04:30等独立缓存。实际会话加密、扩展表选择、设备接受和物理效果继续标未验收，不必把这些未知伪装成已完成。

本批不新增运行时接口或发送，SDK仍0.7.29/原生0.3.29；完整命令和高级开发门槛false。
