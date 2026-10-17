# 独立配置输入源与数值（0.7.11 / 原生0.3.11）

已有RS4Mini/RSGimbal统一入口的设备SDK增加getStandaloneTuning/setStandaloneTuning，Python另有get_standalone_tuning/set_standalone_tuning别名。Web共享JS实现，没有新增页面按钮或高级运动任务。必须显式选择ronin-2.2.2来源配置。

## 源码证据与边界

固定Ronin 2.2.2/7096 APK恢复的UI中，supportProfileStandalone经CommonUtils的代际判断到产品缓存ModelName等于Model.HG724的条件分支。这是App中的条件关联，不是BLE型号字段或本机实时读数。底层performParamSet把gimbal_input_source=2与六个命名字段之一放入同一个DataGimbalSetUserParams请求；不拆成两次写入，也不把普通RC字段当作别名。

| parameter | Pitch / Roll / Yaw索引 | 宽度与源码整数范围 |
|---|---|---|
| speed | 80 / 79 / 81 | size2，0..100 |
| smoothing | 77 / 76 / 78 | size2，0..30 |

input_source为index72/size1，资源范围0..3，但本路径只证明写入2。数值字段资源typeID=0且size2，编码按实际宽度取整数低两字节小端；不能按类型名称推断size1。范围不表示物理速度、百分比或机械安全保证。

## 调用契约

```js
// 仅供明确授权的实机会话；离线测试不连接设备。
gimbal.appCommands.useProfile('ronin-2.2.2');
const raw = await gimbal.appCommands.getStandaloneTuning();
const one = await gimbal.appCommands.getStandaloneTuning({axis:'roll',parameter:'smoothing'});
const ack = await gimbal.appCommands.setStandaloneTuning({inputSource:2,axis:'pitch',parameter:'speed',value:20});
```

读取可按axis/parameter筛选，默认speed三轴然后smoothing三轴，共六项；04:10请求总是先含72。返回inputSourceRaw及values，不为了读取而切换输入源，不声称一次响应提供原子预设快照，也不根据当前输入源推断值已属于source2。

写入四个字段都必须显式指定，仅允许inputSource:2、命名轴pitch/roll/yaw、speed/smoothing及范围内整数；拒绝布尔、任意索引和未知字段。例如Pitch速度100的04:0F体为48010250026400：72/size1/2，随后80/size2/100的小端值。没有单独输入源切换接口、任意多参数写入或失败回滚。

两种方法timeoutMs默认3000，允许>0..60000。写入先停止主机运动并独占到相关ACK；取消、超时、断线不重放，不发送猜测的源恢复。ACK不证明设备生效、物理完成或持久化。activePresetVerified、deviceVerified、physicalCompletionVerified保持false。未知输入源（例如255）和越界数值（例如65535）保留，不夹取后写回。

Node/Python查询沿用现有有限查询并发机制；原生查询占用操作槽并先停止。原生接口getStandaloneTuning:timeoutMs:completion:与setStandaloneTuning:timeoutMs:completion:接收相同命名字典。各端共用自身连接、队列、序号与取消机制。

## 复现与未验收项

证据为protocol/research/ronin-standalone-evidence.json；tools/research/ronin_standalone_trace.py复核固定APK及SDK/UI两段哈希，调用已有42方法数值审计，再固定6个型号条件方法指纹。没有执行厂商代码、扫描或连接设备，APK/派生DEX不入Git。

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_standalone_trace.py --apk work/research/dji-ronin-2.2.2.apk --sdk work/research/code-banks/business-05-code-restored.dex --ui work/research/code-banks/business-03-code-restored.dex --output work/research/standalone-reproduced.json
```

实机仍需逐项核对固件、活动预设、输入源改变的含义、ACK/回读/App显示、真实效果和重启持久化。新接口不证明全协议完整；全部命令与高级新增门槛保持false。
