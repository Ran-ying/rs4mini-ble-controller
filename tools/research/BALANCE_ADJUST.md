# 04:40平衡调整：请求、状态及旧视图调用

2026-10-19。固定Ronin2.2.2 APK和六段恢复DEX的只读审计；不执行Java/JNI/APK/UI、不提供SDK收发、不操作硬件。运行时仍0.7.32/原生0.3.32。工具[ronin_balance_adjust.py](ronin_balance_adjust.py)，证据[ronin-balance-adjust-evidence.json](../../protocol/research/ronin-balance-adjust-evidence.json)。

## 同一命令的两种业务

CmdIdGimbal的BalanceAdjust构造参数为`[BalanceAdjust,29,64,0,1,DataGimbalGetBalanceAdjustPushInfo]`：29是ordinal，64是命令号04:40；接收类与发送类DataGimbalBalanceAdjust不同。不能再将40响应简单写作“无已知字段”，也不能把源码绑定当本机BLE采样。

发送类构造业务体为type一字节、length窄化字节、数据。命名setGimbalAdjustRequest固定ADJUST_REQUEST=0、length=1，第三字节为下表值；doPack不再次填充。start指定APP→GIMBAL、receiverId0、REQUEST、ACK.YES、Encrypt.NO及repeatTimes1。这是业务类条件加密前设置，不证明最终线上明文或固件接受。

| 源名称 | 请求值 | 候选业务体 |
|---|---|---|
| PITCH_TEST | 1 | 000101 |
| PITCH_ADJUST | 2 | 000102 |
| ROLL_TEST | 4 | 000104 |
| ROLL_ADJUST | 8 | 000108 |
| YAW_TEST | 16 | 000110 |
| YAW_ADJUST | 32 | 000120 |
| STOP_ADJUST | 64 | 000140 |
| OTHER | 100 | 000164 |

OTHER是源枚举回退项，不是允许的目标设备动作。表中没有DUML帧、实机抓包或安全范围。

## 状态的十进制字符串转换

接收setPushRecData首先调用父类，然后仅检查非null且长度>1；读取type0、length1，但不验证length值。type=0时直接读第2字节并继续读取advice的3/4/5偏移。完整候选业务布局至少6字节；源长度2会访问越界，其他短体可能走父类补零，不能照搬到SDK。未知type不刷新静态结果字段，源单例可能保留旧状态；离线工具返回None，不模拟旧值。

第2字节被BytesUtil.getBinaryStrFromByte转换成8个字符，按两字符分段，再用**没有radix2的Integer.valueOf(String)**解析，所以源值是0、1、10、11，不是0、1、2、3：

| 第2字节位 | 源字段 | 枚举值 |
|---|---|---|
| bits0..1 | test status | 0 TEST_NOT_IN_PROCESS，1 TEST_IN_PROCESS，10 TEST_FINISHED，11 TEST_ERROR |
| bits2..3 | pitch result | 0 DEFAULT，1 PERFECT，10 OKAY，11 BAD |
| bits4..5 | roll result | 同上 |
| bits6..7 | yaw result | 同上 |

此布局与balance_test/index37的状态/结果位顺序及枚举不同，不共用解码表。偏移3/4/5分别为Pitch/Roll/Yaw建议原值。建议源枚举为NONE0、UP4、DOWN12、FORWARD16、BACK48、UP_FORWARD20、UP_BACK52、DOWN_FORWARD28、DOWN_BACK60、LEFT1、RIGHT3、OTHER100；不能猜成连续序号。

以上是源业务方法偏移。当前没有独立验证RS4Mini线上请求/推送/ACK的对应偏移、分发与返回码剥离，不把这些字段直接加入运行时解析。

## 调用与生命周期边界

六段扫描找到6个类外直接调用方法，均在GimbalAdjustView及内部类；参数/返回类型提及另行记录，避免把带枚举参数的其他方法误判为命令类调用。唯一直接命名发送包装是sendGimbalAdjustRequest→getInstance→setGimbalAdjustRequest→start。测试/调整三轴和STOP在视图中分别使用；这些是源请求，不等于本机原生单轴回中。

onAttachedToWindow在缓存MotorEnabled为true时尝试setGimbal(false)，随后注册事件并初始化界面；不是先确认电机已经关闭。日志名包含Ronin_sc，退出路由为ConfigSettingBalanceTestHG701，但日志或视图名均不能单独证明支持/不支持HG724。未定位完整型号入口。

请求回调成功后测试分支启动本地20秒Observable.timer。错误、完成、超时处理会发STOP_ADJUST；窗口detach只注销事件/处置本地timer/关闭进度框，没有直接发送STOP。收到成功ACK、本地timer结束或窗口离开，都不能当成固件物理停止。不得自动引入该UI流程、电机切换、轮询、等待完成或主机运动组合。

## 复现与剩余工作

```sh
PYTHONPATH=work/research/analysis-libs:tools/research work/python312/bin/python tools/research/ronin_balance_adjust.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/code-banks \
  --output work/research/reproduced-balance-adjust.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_balance_adjust.py -v
```

工具先校验所有输入哈希，提取61个方法指纹、枚举/字段/调用事实；输出不含完整厂商方法。测试覆盖256 packed值、256 length值、未知type、短体拒绝、十进制转换和调用目标分类。段01/07、残余保护桩、反射/native/其他类加载器尚未排除。HG724入口、实际包层和通知、状态关联、物理动作/中止及恢复仍需证据。

现有HG724继承的balance_test/index37通过04:0F/10，保持[原研究](BALANCE_TEST.md)及[现有SDK](../../docs/APP_BALANCE_TEST.md)边界；本研究没有用04:40替代它。48项清单、全部命令与高级开发门槛仍未通过。


后续[平衡入口条件审计](BALANCE_ENTRY.md)进一步限定HG724普通菜单走视频页；不是全局不支持04:40的证明，原61方法证据不改写。
