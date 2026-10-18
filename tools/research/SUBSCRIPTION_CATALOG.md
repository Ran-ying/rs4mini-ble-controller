# 完整命名订阅注册目录与初始化条件

2026-10-18，运行时仍Node/Python/Web0.7.25、原生0.3.25/build28。本批只提供只读研究工具和显式条件下的业务体分析，不构造DUML帧、不导入SDK、不执行厂商代码。
固定APK/bank05与res/DB.json，24方法指纹；证据为[ronin-subscription-catalog.json](../../protocol/research/ronin-subscription-catalog.json)。前置打包/接收审计见[SUBSCRIPTIONS.md](SUBSCRIPTIONS.md)。

## 152个注册调用不是152条命令

所选Ronin2SubscribeIMPL构造器含152个不同键：110处通过BaseCommand，42处通过显式命令/频道。BaseCommand目录81项；其中89个键使用显式BaseCommand编号、21个键依赖元数据读取。
在所选res/DB.json存在且源支持条件为true的分析分支中，命令空间分布为04:10的98个键、04:32的12个键、04:66的42个键，合并成121个命令/频道对，存在17组别名。
不同键可指向同一位：反向/映射状态共用频道，多个位设置共用一个参数；PeripheralGyroOutYaw和PeripheralGyroAccePitch共用66/21，仍保留上一批的源类型歧义。
本批不据键数推导设备能力数，不把此构造器当全App动态注册或固件完整目录。

## 三种BaseCommand构造不能混用

- (name,ordinal,parameterName)：默认推送类GetUserParams，调用DJIGimbalParamInfoManager.read(parameterName)；非空时才取index写入mId，空时保留Java实例int默认0。
- (name,ordinal,id,parameterName)：显式id，默认推送类GetUserParams。
- (name,ordinal,id,parameterName,pushClass)：显式id和推送类。

源put先比较推送类是否GetUserParams，匹配走10，否则走32；本固定注册目录实际只见GetUserParams和RoninGetUserParams两类，工具拒绝额外未知类，不猜其业务。
ordinal不是频道，DataType.mId和CmdId.value也分别追到字段/构造字面量。普通用户参数、Ronin电机参数、外设DataType三个空间不合并。

21个资源条件键对应15个BaseCommand，包括ControllerMaxSpeed三轴、Ronin2角度上下限六项、IsChannelNRev/ChannelNMapState六组别名。
在所选DB资源存在的候选中，它们使用41..43、47..58等频道；如果初始化时read返回null，就不是这些编号，而是0。资源在APK存在，不等于枚举初始化前该管理器已加载它。
当前没有证明真实资源加载顺序，也没有把null默认0或文件中的预期编号静默固化成SDK发送表；目录逐项记录channelSource和missingMetadataChannel。

## 两处型号缓存条件

FollowModeSensitivity和GimbalControlState的注册分别受isSupportStateSince4Gen判断控制。工具保留两个独立条件区间，不将条件泄漏到其后无条件注册。
该函数按DJIComponentManager的GimbalComponentType做switch：DF101_HANDLE、DF101_WHEEL、HG701、HG702、HG703、HG710、HG711、HG720、None、Ronin2、Ronins返回false，默认分支返回true。
固定声明中HG724走默认true；这不是运行时型号识别或“4代安全白名单”。None明确false，其他未知/缺失状态不作统一结论；没有读取当前组件缓存或执行switch初始化。

## 显式条件的离线快照

工具snapshot只生成命名选择的业务体：命令组排序、组内位图去重，布局沿用commandByte/最高频道/LSB位图，不编码完整帧。
选择资源条件键时必须给metadata_case='db-present'或'missing'；选择条件键时必须显式给state_since4gen=True。该布尔只表达稳定分析分支，不模拟两次调用之间缓存变化。
空键集合拒绝，不能用空体宣称远端退订。重复名字或别名可以去重为同一位，但不消除字段语义的歧义。

| 命名选择及条件 | 业务体 |
|---|---|
| UserProfile、PitchMotorControlStiffness、PeripheralPosYaw | 10000132000166240000000010 |
| ControllerMaxSpeedYaw，DB-present | 1029000000000002 |
| ControllerMaxSpeedYaw，元数据缺失 | 100001 |
| PeripheralGyroOutYaw、PeripheralGyroAccePitch | 6615000020 |

全152键在DB-present/support=true分支生成36字节、121个位；元数据缺失分析分支合并成106个位。这些是源码条件模型，不是抓包、源程序执行或本机采样。
源目标仍为APP→CENTER/id7（接收字节E5）、04:12且不请求ACK；1秒刷新、最后组移除后本地停发不证明租期、远端替换或停止。参见前置订阅审计。

## 未完成项

SDK发送允许列表没有扩大，未增加订阅对象、自动刷新、远端退订承诺或高级功能。下一步需要核对管理器加载与枚举初始化顺序、真实组件缓存及目标路由，之后再固定运行时契约。
没有扫描/连接/移动硬件、运行UI或执行厂商代码；全命令与高级门槛仍false。

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_subscription_catalog.py --apk work/research/dji-ronin-2.2.2.apk --bank-dir work/research/code-banks --output work/research/ronin-subscription-catalog-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_subscription_catalog.py -v
```

19项新增检查覆盖构造/资源缺失分支、显式型号条件、别名/位图/全目录、重复或未知注册、未支持寄存器覆盖、switch字段来源及哈希预检。APK/恢复DEX/完整反汇编留在忽略目录，不进入Git。
