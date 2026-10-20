# 原生动作程序：当前App通用请求体与状态

2026-10-18，运行时/安装包仍0.7.21 / 原生0.3.21。本批只读固定Ronin APK六段恢复视图，
工具`ronin_program_trace.py`不导入SDK、不构造DUML帧、不发送、不执行厂商代码。
[证据JSON](../../protocol/research/ronin-program-evidence.json)记录106个方法指纹、60个类外直接调用方法。
这些调用方法位于bank03的Create界面、辅助类与任务检查类；没有据此建立HG724界面可达性或本机支持。
银行1/7、残留保护方法、反射/动态路径与固件不在完整覆盖内。

## 命令与范围

| 命令 | 固定源实现 | 本批确认 |
|---|---|---|
| 04:62 | DataGimbalSetTrackStatus | 路点请求、1字节停止候选及源ACK请求 |
| 04:25 | DataGimbalSetDelayTimelapseParams | 旧延时info字节、最多6点、外设控制位 |
| 04:37 | DataRonin2SetTimelapseParams | 另一版延时、最多5点、时长覆盖及模式分支 |
| 04:63 | DataGimbalSetPanoramaParams | 10字节混合宽度请求，含拍摄参数 |
| 04:64 | DataGimbalGetPushPanoramaStatus | 独立5字节业务体的状态及两个16位计数 |
| 04:38 | DataGimbalGetPushTimelapseStatus | 独立4字节业务体的状态、预览与进度 |
| 04:6B | DataGimbalGetPushExternalStatus | 状态订阅/停止订阅/单次请求，以及多程序记录 |

所有偏移均指所选源码的业务字节数组，尚未逐条证明BLE原始payload偏移、返回码剥离或本机布局。
构造器中ordinal不是wire命令值。106指纹包括上述类、内部类、命令枚举构造及三种BytesUtil整数转字节方法。
“读取源代码”和“已对本机封装并验收”分开记录；本批不扩大任何发送允许列表。

## 04:62路点

`addRoadPoint`的五个float参数依次为moveTime、stopTime、yaw、pitch、roll；内部RoadPoint构造器的顺序不同，
不能照构造器签名误排公开添加方法。UI的字段取值与调用顺序提供了交叉核对。

phase=0时长度为2+10*N。byte0是(tripod<<1)|(phase<<2)|(recordOrPreview<<3)，byte1为点数。
每点依次为moveTime、stopTime、roll、pitch、yaw，各取float32乘10、Math.round(float)后的Java int低16位，小端。
Math.round的负半数向正无穷舍入，不是Python round或原生角度04:14的截断；没有源码范围夹取。
最多10点，超出时addRoadPoint直接返回原对象，不追加。离线工具拒绝超过10点的输入，避免悄悄丢点。

phase=1只打包byte0，立即返回，不清空原点列表；phase=0打包后clearPoint。
其他非零int分配1字节却继续写byte1，不能把全部非零值自动当成有效停止；离线模型只接受0/1。
源码start请求ACK并设置repeatTimes=5/timeOut=1000，这些是源参数，SDK没有照搬自动重试。
CreateTrackView预览入口传recordOrPreview=1，启动phase=0，停止phase=1；这不是本机“预览绝不会控制相机”的证明。

## 两版延时不能合并

04:25的每点10字节：duration低32位、roll/pitch/yaw三个signed short，小端。
addRoadPosition检查已有size>5才拒绝，所以可加入第6点；不能按常量5误报容量5。
info字段bit0 mode、bit1 tripod、bit2 phase、bit3 preview、bit7 externalDevice。
各setter先OR已有info，不清除旧位；给已置位字段再传0/false不会清位。doPack之后清点并把info清零。
CreatePathDelayView的externalDevice位涉及对焦电机连接和相关开关，不按名字改成通用运动开关。

04:37的addRoadPosition在已有size>=5时拒绝，因此最多5点。
mode bit0=1时只发2字节，仍携带当前队列点数、不序列化点；bit0=0时长度2+10*N，
每点duration来自Java long但只复制低4字节，roll/pitch/yaw来自int但各复制低2字节。
点序列写完后，源码又将总mDuration低4字节复制到offset2，覆盖首点duration。
N=0且bit0=0时分配2字节后仍向offset2复制4字节，会越界；离线工具明确拒绝，不擅自扩容“修正”源行为。
成功走到结尾后清点和info。长整型时长的单位、总时长与首点覆盖的业务含义仍需UI/型号路径审计。

## 04:63全景

固定10字节：left低16位@0、right低16位@2；top@4、bottom@5、horizontal@6、vertical@7、exposure@8、command@9均低8位。
源`setRange`参数顺序为left/top/right/bottom，不能直接按包内顺序调用。没有按字段名推断角度单位或物理范围。
CreatePanoramaView停止入口给command=0，但启动方法从外部传入command，其他值需追调用者。
该命令混合曝光/拍摄数量字段；只有离线核对，不提供相机控制或全景SDK发送。

## 独立状态与6B复合状态

04:64业务体：byte0原始状态；offset1/3两个uint16 LE计数。
04:38业务体：byte0&3为状态，bit3为takingOrPreview整数0/1，byte1/2/3为完成点/当前路段/总进度原值。
源TimeLaps枚举NONE/PREPARE/PROGRESS/END/ERROR为0/1/2/3/4，find未知回退NONE；
两位状态getter不能返回ERROR=4，不能偷偷把掩码改为7以迎合枚举。
这两个类的isChanged会调用start发送ACK（非请求、无需ACK），并非仅更新缓存。
研究工具不执行该自动ACK；以后接SDK时必须显式区分被动解码和响应发送责任。

04:6B请求体为00、requestType、01、programCommand，type=0持续推送、1停止持续推送、2单次推送；
默认值是持续推送。停止订阅不是停止电机或程序，不能由此宣称物理取消。
所选源程序tag为62/37/63；25没有这个解析分支，不按“同为延时”混用。

setPushRecData对长度<=1直接返回，旧success与其他字段可能保留；长度>1时首字节0或1均设置success=true，其余false并返回。
之后按tag、length、payload循环；源tag/length直接aget-byte，有符号，无完整长度验证。
62记录至少4字节：status/finished/current/total；37至少4字节：flags&7、bit3整数0/1、finished/current/total；
63至少5字节：status、current uint16、total uint16。注意37记录的状态掩码7与独立38的掩码3不同。
多条记录会覆盖同一单例的相应字段，其他程序字段保留，不能把全部getter当同一时刻的新快照。

离线`external_status_records`是有完整边界检查的分析视图：保留全部重复/未知tag、记录内未知尾字节和原始字节，
拒绝不完整记录、已知记录过短和源有符号length>=128的情况；它没有复制源的跨记录读取/缓存保留行为。
这不是通用BLE解码器，不解释未知状态为完成，也没有自动确认ACK、完成待处理请求或结束运动。

## 复现与后续

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_program_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/code-banks \
  --output work/research/ronin-program-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_program_trace.py -v
```

哈希先验证、再加载可选解析器；手写向量只核对已人工阅读的有限源字段，没有执行厂商指令或做完整符号执行。
仍缺HG724页面选择、型号支持条件、参数单位/范围、接收路由/返回码、程序标识与状态关联、
完成/停止/断线效果及相机/外设分支隔离。本批不等于固件程序可用，不新增高级组合，全部命令门槛false。

离线track向量仅接受有限float与源UI使用的0/1字段子集；不模拟全部Java int、NaN/Infinity或源单例状态。

## 后续：八段程序重审（2026-10-20）

见 [PROGRAM_PREFIX.md](PROGRAM_PREFIX.md)。
