# 04:27异常状态与04:33电量源布局

2026-10-17，固定六段恢复视图，36方法指纹与2类外直接调用方法见
[证据](../../protocol/research/ronin-status-evidence.json)。只读静态研究，未执行厂商代码或操作硬件。

DataGimbalGetPushAbnormalStatus和DataGimbalPushBatteryInfo均直接继承DataBase，未覆盖公共收包/get路径。
请求型未加密体通过RecvPack→setPushRecPack→setPushRecData→setRecData原样进入_recData；
Integer的一字节读取经BytesUtil.getInt/fillBytes/arrayComb补零高位，按LITTLE_ENDIAN读取，无符号0..255。
ACK/错误包不能套用相同业务偏移；SDK候选只接收未加密请求型消息。

21个异常直接getter均读一字节、右移再掩码；5个返回int，其余返回masked==1的bool。

| 业务偏移 | 右移/掩码 | 源getter |
|---|---|---|
| 0 | 0/1，1/1，2/1 | isRollLocked、isPitchLocked、isYawLocked |
| 1 | 0..7/1 | isJointLockAfterStartup、isJointLockWhenStartup、isMotorProtected、isErrorRecentWhenStartUp、isUpgrading、isYawLimit、isErrorRecentOrSelfie、isPanoReady |
| 2 | 1/1，2/1，3/1，4/1，5/1 | getFanDirection、getVerticalDirection、isInFlashlight、isPortrait、getGimbalDirectionWhenVertical |
| 3 | 0/1，1/3，5/1，6/1 | isPhoneOutGimbal、getGimbalGravity、isYawLimitedInTracking、isPitchLimitedInTracking |
| 4 | 0/1 | getSleepMode |

isGimbalLocked另调用isRollLocked/isPitchLocked并作OR，不包含Yaw；不能按名字改成三轴OR。
getGimbalGravity保留2bit值0..3；getSleepMode是int0/1，不根据名字改成旧RS3休眠布局。
最少5字节只是全部已知getter需要的长度，不是本机报文长度认证。未知位和尾字节保留。

RobinPushBattery源枚举wire51（0x33）绑定DataGimbalPushBatteryInfo，getCapacityPercentage直接返回偏移0/宽1的Integer。
源代码没有0..100夹取或255错误码处理；SDK仅保留rawCapacityValue，不显示或承诺其为本机百分比。
这与0D:02其他型号候选不是同一个命令/布局。

六段类外直接调用只见DJIGimbalMobileHandheldAbstraction的异常事件与同步方法，消费gravity/motorProtected/phoneOut等字段。
本次未定位battery类外直接调用，也未建立HG724布局路径；类绑定、枚举和零引用均不是型号支持或不支持证明。
原始App还包含未恢复banks1/7、保护桩/动态路径，完整覆盖条件未满足。

0.7.21在显式App来源下实现这两种被动候选，见[SDK说明](../../docs/APP_SOURCE_STATUS.md)。
不触发订阅、请求、自动告警/停机、升级、校准或全景动作，不把源标志当动作完成。

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_status_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/code-banks \
  --output work/research/ronin-status-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_status_trace.py -v
```

工具先验证全部哈希，静态识别一字节Integer、移位/掩码与bool返回后缀，拒绝反向分支、未知类型/变换。
其他关键方法固定指纹并人工静态核对，不是通用CFG/虚拟机，不保存厂商反汇编或构造DUML。
全部命令与高级新增门槛仍false。
