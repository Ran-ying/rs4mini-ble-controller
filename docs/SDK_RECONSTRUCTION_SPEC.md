# RS 4 Mini BLE SDK 独立复刻规范

版本：1；日期：2026-10-21；基线：Node/Python SDK **0.7.39**，macOS **0.3.40 / build43**。
代码基线提交：`61f953e6f9f4492745f7fd49a855130d8b26b57b`（运行时代码与`18ccfcf4622e87c8c39686d6ee8ebd3b0b685d1a`相同）。

本文是当前实现的独立重建输入。只给另一位开发者或AI这一个文件，也应能重建相同的BLE收发、保留命令、解码、SDK分层与主要主机组合行为。正文的字节表、算法、参数表、参考代码和测试向量均在本文件内；末尾源码路径用于核查，不是实现算法的外部前置依赖。

这是非官方、依据现有代码与实机记录形成的实现规范，不是DJI完整协议。**复刻当前SDK不等于恢复稳定器所有固件命令。** 当前49项研究清单仍不完整；不要因此添加相机、激活写入、未知参数写入或新的高级功能。

## 1. 复刻范围与层次

```text
应用 / macOS GUI
       ↓ 唯一应用入口 RS4Mini / RSGimbal
主机组合层：moveTo、定时速度、轨迹、路点、保存位置返回、四元数数学
       ↓ 共享同一连接、写队列、操作所有者、停止机制
设备SDK：BleDevice / RSBleDevice
  ├─ 基础速度、回中、原始degree-info、04:05反馈
  ├─ AppCommands：显式ronin-2.2.2来源，普通参数/电机参数/维护请求/四类状态
  └─ ExperimentalDevice：显式其他型号来源，原始查询与研究接口
       ↓ DUML编码 / 分片写队列 / 通知重组 / CRC / 事务关联
BLE GATT FFF0 → 写FFF5 / 通知FFF4
```

- `moveTo()`等是电脑端用反馈和速度命令组成的算法，**没有同名固件定位命令**。
- 主实现为Node；Python用Bleak，原生macOS用CoreBluetooth。GUI不拼帧、不越过SDK直接写蓝牙。
- 下述所有`index`、宽度、位号、范围表默认用**十进制**；标记`0x`或两位十六进制的命令、报文示例用十六进制。
- payload偏移从0开始。未另说明的多字节数值为小端序。保留原始值、未知位、未知记录，不能用0或“成功”替代未知/缺失。
- 数据对象应独立复制；原始消息、缓存副本、观察者参数之间不能共享可写内存。

## 2. 蓝牙通道、连接与权限

| 项目 | 值 / 行为 |
|---|---|
| BLE服务UUID | `FFF0`，完整写法`0000fff0-0000-1000-8000-00805f9b34fb` |
| 设备→电脑特征 | `FFF4`，订阅Notify |
| 电脑→设备特征 | `FFF5`，Write Without Response |
| 名称筛选 | 默认`DJI RS4 MINI`；Node比较前转大写并去掉所有空白，使用包含匹配 |
| 写分片 | 当前实现每片最多20字节；即使系统允许更大MTU也仍用20 |
| 通知边界 | 任意分片/合包，不保证一通知一DUML帧 |
| 速度重发 | 默认15Hz，即约66.667ms间隔；写入有背压，不能并发交错分片 |
| 常见反馈频率 | 实机04:05约1Hz；不是固件频率保证 |
| Node最低运行时 | Node18+，包`@stoprocent/noble`；标准API异步返回Promise |
| Python | 3.8兼容，Bleak；async接口；macOS缓存UUID连接须走实际CoreBluetooth标识检索 |
| macOS | Foundation/CoreBluetooth设备SDK；AppKit仅GUI；有蓝牙使用说明和用户授权 |

传给GATT写入的是DUML原始字节，不额外加JSON、文本hex、ATT操作码或HCI包头。底层库负责GATT/ATT传输。比如22字节停止帧拆成20+2字节写入；不能给每一片重新添加DUML头和CRC。Write Without Response指GATT写本身，不表示DUML命令没有应用层ACK。

Node连接过程：惰性初始化蓝牙→等待poweredOn→有本机缓存标识时优先直连→失败且总期限未到则扫描→找到名称匹配设备→连接→发现FFF0及FFF4/FFF5→先挂通知回调，再订阅FFF4→清空旧解码器和遥测缓存→标为ready。未完成订阅不能发布“已连接”。不添加当前SDK不存在的DUML握手、激活、口令、自动订阅命令。

Node默认`connect(timeoutMs=30000,directConnectTimeoutMs=5000)`，总timeout覆盖等待电源、扫描、连接、发现和订阅，而非每阶段重新计时。GATT单次I/O/清理默认3000ms。SDK实例独占其适配器；不要把多个控制端同时连到同一控制通道。设备ID、序列号和用户原始抓包只在本机保存，不内置到复刻代码。macOS外设标识是CoreBluetooth UUID，不是跨系统通用的蓝牙MAC；Node缓存通常去掉横线转小写，Python/原生使用规范UUID检索，不应跨电脑硬编码复用。

Python的macOS缓存UUID：用CoreBluetooth retrievePeripheralsWithIdentifiers检索外设，转换为带(peripheral,manager) details的Bleak BLEDevice再连接；Bleak0.22需要rssi参数时传None，不能伪造测量值。找不到才退回原地址路径；非macOS及注入客户端不依赖此桥。原生macOS构造时创建central（测试时可注入fake），30秒连接总期限内先按FFF0及1812检索已连接的同名外设，再全服务扫描；1812只用于检索现有系统连接，实际控制仍只用FFF0/FFF4/FFF5，不发送HID数据。

macOS默认Noble/Bleak关闭时取消本central的连接即可，避免多余的`setNotify(false)`：实测设备拒绝该取消通知写入。其他平台、通用适配器和注入测试客户端保留显式unsubscribe行为。真实断开/停止错误不能被吞掉。原生CoreBluetooth关闭由其central取消连接。

## 3. DUML外层格式

一帧总长度`L=13+len(payload)`，允许13..1023字节。发送器固定头如下：

| 帧偏移 | 长度 | 内容 |
|---:|---:|---|
| 0 | 1 | `0x55` |
| 1 | 1 | `L & 0xFF` |
| 2 | 1 | `0x04 | ((L >> 8) & 3)` |
| 3 | 1 | CRC8，覆盖帧0..2 |
| 4 | 1 | sender地址字节 |
| 5 | 1 | receiver地址字节 |
| 6 | 2 | sequence，uint16 LE |
| 8 | 1 | flags |
| 9 | 1 | commandSet |
| 10 | 1 | commandId |
| 11 | N | payload |
| L−2 | 2 | CRC16 LE，覆盖帧0..L−3 |

解析长度用`packet[1] | ((packet[2] & 3) << 8)`。发送固定版本位`0x04`；当前解析器并未额外以高版本位拒帧，复刻严格兼容时不要悄悄加入不同的版本判定。

| 端点 | 线上字节 |
|---|---|
| 电脑App | `02` |
| GIMBAL | `04` |
| CENTER/id7特殊接收端 | `E5`，不是直接写枚举值7 |

常规发送`02→04`，响应/推送通常`04→02`。CENTER只读请求为`02→E5`、响应`E5→02`。

常见flags：普通速度及自动调参发送`00`，查询/参数写/回中/微调/水平校准发送`40`，ACK通常`80`。判断ACK用`flags & 0x80 != 0`；当前结构化App ACK还要求`flags & 7 == 0`。四类App推送要求`flags & 0x87 == 0`（非ACK、无低三位加密标志），不能把ACK业务体当推送。

当前SDK不实现会话加解密。带低三位加密标志的帧仍可进入通用原始消息回调，但不进入上述结构化App解析或04:05姿态解析。不要声称“所有固件永远明文”，也不要因看到`40`就剥掉任意字节或尝试解密。

CRC算法均反射、无最终异或：

```text
CRC8:  初值0x77；逐字节XOR；8次：最低位1则 (crc>>1)^0x8C，否则 crc>>1；结果&0xFF
CRC16: 初值0x3692；逐字节XOR；8次：最低位1则 (crc>>1)^0x8408，否则 crc>>1；结果&0xFFFF
```

序号从`0x0100`开始递增、uint16回绕。分配时跳过仍在pending表中的序号。停止帧和所有其他发送也使用同一个序号源。

### 3.1 收包重组

1. 将每次Notify字节追加到流缓存，默认上限8192字节。
2. 找到第一个`55`，前面的字节计入discardedBytes并丢弃；无`55`则清空。
3. 不足4字节等待；长度不在13..1023或头CRC8错误，则丢1字节、invalidFrames加1，重新找头。
4. 不足声明长度等待；够长则校验全帧CRC16。
5. CRC错误同样只丢1字节重同步；成功取出整帧并继续处理剩余缓存。
6. 缓存超过8192时尽量从最后一个`55`保留；若仍超限则清空。断线/新会话重置缓存和计数。

### 3.2 查询关联与ACK

事务关联始终启用，不依赖研究profile是否开启；App查询也共享这张表。发送前登记`pending[sequence]={session,expectedSender,commandSet,commandId}`；只有同一会话、同sequence、正确命令对、sender为原请求receiver、receiver=02、ACK位为1才完成原始响应等待。然后由各业务解析器验证加密标志、长度、返回码。最多64个pending；超出报BUSY。未关联、迟到及重复响应只走原始通道，不完成另一个请求。

普通App业务ACK的payload：`ccode:u8 | body:bytes`。`ccode=00`才是本SDK接受的成功，其他值报DEVICE_ERROR并附原始响应；空payload或格式错误报PROTOCOL_ERROR。**ccode只在ACK中剥1字节；主动推送绝不统一剥1字节。** ACK成功只是请求层结果，不自动标记物理任务完成。

原始`version/controlStatus/type/degreeInfo`查询仅返回原始消息；不把它们自动套进App参数ACK解析器，不承诺业务字段已解释。

## 4. 当前保留的全部发包命令

`主`表示当前常规SDK；`研究`表示仍在显式其他型号实验接口中，必须独立隔离，不作为RS4 Mini已验证控制能力。表内payload之后均由第3节包装CRC/地址/序号。

| 层 | set:id（hex） | 发送flags | payload | 响应/完成依据 |
|---|---|---|---|---|
| 主 | `04:01` | `00` | 9字节RC速度，第5节 | 不等待ACK；反馈另走04:05 |
| 主 | `04:4C` | `40` | `FE 01` | 只保证发送；原实现不等待ACK或自动判到位 |
| 主 | `04:1E` | `40` | 空 | 关联原始ACK |
| 主 | `04:10` | `40` | 参数index字节列表 | 同命令ACK，第6节 |
| 主 | `04:0F` | `40` | `index,size,valueLE`记录拼接 | 同命令ACK；ccode后body不强行解释 |
| 主 | `04:32` | `40` | 单个电机index | 同命令ACK；专用电机表 |
| 主 | `04:31` | `40` | `motorIndex,01,value` | 同命令ACK |
| 主 | `04:6A` | `00` | `00 01 start`，start=00/01 | 不请求/等待ACK；04:6E推送观察 |
| 主 | `04:08` | `40` | `00`，仅AUTO | 同命令ACK；先电机前置检查；04:30另观察 |
| 主 | `04:07` | `40` | `signedTenths,axisCode` | 同命令ACK |
| 主 | `04:6B` | `40` | `00 02 01 programId` | 同命令ACK；不执行程序 |
| 主 | `00:32` | `40` | `01`或`11`，receiver=E5 | 同命令CENTER ACK；显式版本布局 |
| 研究 | `00:01` | `40` | 空 | version原始ACK |
| 研究 | `04:0B` | `40` | 空 | controlStatus原始ACK |
| 研究 | `04:1C` | `40` | 空 | type原始ACK |
| 研究 | `04:14` | `40` | RS3绝对角8字节，第11节 | 仅写后观察等待，不代表到位 |
| 研究 | `04:0C` | `40` | RS3原生速率7字节，第11节 | 定时发送及release，不代表目标设备支持 |
| 研究 | `04:0F` | `40` | `23 01 sleepValue`，其他型号来源 | 原始写后返回，不等待业务ACK |

不能把研究sleep包与普通电机参数35的读改写当作相同语义。

## 5. 基础速度、停止、回中、遥测

### 5.1 三轴速度04:01

`pan/tilt/roll`输入默认0，裁剪到−1..1。Node会先按`Number()`转换有限数值；数学映射为：

```text
RC(u) = 1024 + floor(clamp(u, -1, 1) * 660 + 0.5)
```

这里的floor实现JavaScript `Math.round`的半值朝正无穷，不能直接换成Python的银行家round。线上顺序：

| payload偏移 | 宽度 | 内容 |
|---:|---:|---|
| 0 | 2 | tilt RC，int16 LE |
| 2 | 2 | roll RC，int16 LE |
| 4 | 2 | pan RC，int16 LE |
| 6 | 2 | 固定0 |
| 8 | 1 | 固定`02` |

非零速度先立即写一帧，再默认每1/15秒重发；写入慢时顺序等待，不突发追赶。`stop()`取消当前操作/连续流、把本地速度置0、使旧运动epoch失效，再发**三帧中位速度**，每帧后等待1/rateHz。中位是`00 04`（1024），不是线上数值0。若RS3原生rate正在使用，先发一次release再发三帧中位。

普通stop不等于固件调参、校准或程序的通用中止命令；不应伪造该保证。

### 5.2 回中04:4C

payload `FE 01`，先停止连续主机运动，Node/Python发送后再按操作收尾发中位帧；原生macOS是先完成三帧中位停止、再写FE01，没有相同的后置三帧保证。`FE`为保留模式值，`01`为reset布尔源值；不是“第254轴”。没有公开单轴回中，不能改成FE04或套旧枚举。回中API只保证写入完成。

回中参照不是机械关节Yaw零点。已测示例：中位Yaw91.60°→偏离107.37°→回中91.61°，用户确认正常；不能要求回中读数为0，也不把这次0.01°差值当普遍精度保证。

### 5.3 04:05反馈

当前结构化遥测要求`set=04,id=05`、flags为0..255且`flags & 0x87 == 0`，payload至少6字节。**Node当前04:05解码函数本身不检查sender/receiver**；原始通道和事务关联另有端点检查。若复刻时额外增加04:05端点限制，应明确作为行为变化，不能宣称逐项兼容。

| payload偏移 | 类型 | 解码 / 条件 |
|---:|---|---|
| 0,2,4 | int16 LE | attitude pitch/roll/yaw各÷10°；至少6字节 |
| 6 | uint8 | modeFlags，缺失为null |
| 7 | int8 | rollAdjust，缺失为null，不用于定位 |
| 8 | int16 LE | yawAngle辅助字段÷10°，缺失为null，不用于定位 |
| 10,11 | uint8 | limitFlags/stateFlags，缺失为null |
| 16 | int16 LE | joint yaw÷100°；关节组要求至少24字节 |
| 20,22 | int16 LE | joint pitch/roll各÷10°；不足24字节时整个jointAngles=null |
| 24,28,32,36 | float32 LE | 至少40字节才给四元数原始分量及norm，分量顺序未验证 |

常见完整payload49字节，但不要硬编码“必须49”而拒绝当前允许的短有效姿态或更长尾部。12..15、18..19以及40以后的字节保留在payloadHex，不猜测含义。

输出包含`attitude`、`jointAngles`、`orientationQuaternion`（缺失可null）、辅助原值、sequence和接收时间。兼容平面pitch/roll/yaw取attitude；机械闭环必须取jointAngles。`getAttitude/getJointAngles(fresh=false)`可返回当前缓存副本；`fresh=true`等下一帧含目标字段的数据，默认3000ms超时。这两个getter的timeout只要求有限正数，不套用App查询的60000ms硬上限。断线必须清空，不能返回上会话缓存。疑似四元数的范数接近1不证明设备轴系或顺序。当前遥测解码不会因float分量出现NaN/Infinity而丢掉整帧；getOrientation才验证范数。参考CLI仅在JSON输出阶段把非有限数转null、负零转0，以匹配JavaScript JSON序列化；原始payloadHex始终保留，内部编解码函数不据此把缺失值补0。

## 6. 普通参数04:10/0F与所有当前参数表

### 6.1 请求上下文决定响应宽度

显式选择`appCommands.useProfile('ronin-2.2.2')`才允许App命令；这是本地来源配置，不是向设备发送协商。

`readParameters({parameters:[{index,size},...]})`要求1..64项，index=0..255，size只能1/2/4/8。**请求payload仅包含index，完全不发送size。** 响应payload格式：

```text
ccode | index0 | headerByte0 | value0[上下文size0]
      | index1 | headerByte1 | value1[上下文size1] | ...
```

headerByte必须原样保存，不能当作可靠宽度。逐项核对index和足够字节数，严格使用本次上下文的size；最后不得有未消耗字节。错误、缺项、次序不符、尾部剩余都报协议错误，不发布半个查询结果。原始size8值保留hex/bytes，避免JavaScript整数精度丢失。

索引150是合法uint8参数，不得把≥128的index误判成负错误码。其他型号旧04:10布局另有负错误码解析，只能放在研究来源，绝不能复用于当前App参数。

普通写payload是一个或多个`index:u8,size:u8,value[size]`拼接。当前命名SDK只开放下列明确映射和写法，不提供任意原始写入入口。

### 6.2 单字节参数

| 名称 | index十进制（hex） | size | 读/写规则 |
|---|---|---:|---|
| followSensitivity | 150 (`96`) | 1 | 写只接受整数0/1；读其他rawValue保留、mode=null |
| customFollow | 132 (`84`) | 1 | 位字段见6.3；读raw保留，写前当前raw必须0..15 |
| motorSettings | 35 (`23`) | 1 | 位字段见6.3；写前当前raw必须0..255 |
| axisMode | 34 (`22`) | 1 | ThreeAxis=0,TwoAxis=8,Roll360=16,ThreeDRoll360=24 |
| smooth yaw/pitch/roll | 17/18/19 (`11/12/13`) | 1 | 读0/1→false/true，其他enabled=null；写严格bool |
| userProfile | 0 (`00`) | 1 | 写整数0..5；读0/1/2源UI名M1/M2/M3，其他null，不擅自命名PF/PTF |
| workMode | 62 (`3E`) | 1 | 写命名Free=0,Flower=1,Fpv=2,Center=3；读未知raw保留、sourceMode=null |
| standalone inputSource | 72 (`48`) | 1 | 独立配置写包固定显式写2；读取实际原值 |

axisMode读取`sourceModeValue=(raw>>3)&3`，据0..3映射四个源名称，unknownBits=`raw & 0xE7`。**写整字节0/8/16/24，不做读改写保留其余位**。名称不证明对应固件运动预设已切换。

smoothTrack写非空轴bool子集；固定按yaw→pitch→roll顺序拼接。未指定的轴不在包里，不补false。例如yaw=true、roll=false：`11 01 01 13 01 00`。读取默认同顺序三轴，亦可按单轴筛选。

workMode读取时withinSourceRange依据raw<=128，虽然128没有命名mode也仍可为true；userProfile依据raw<=5判断源范围。不要将此范围标志当已识别预设。

userProfile与workMode、axisMode、customFollow、smoothTrack是不同域；不自动联动、不保存、不激活其他预设。

### 6.3 位字段读改写

customFollow：bit0 enabled、bit1 pitch、bit2 roll、bit3 yaw；mask=`0x0F`。motorSettings：bit0的**反值**为enabled（bit0=0表示启用），bit4 forbidSelfie、bit5 forbidVertical、bit6 roll360；mask=`0x71`。解码unknownBits=`raw & (0xFF XOR mask)`。

两类setter都要求非空、只含已命名字段的严格布尔patch。事务：预验证/快照→独占操作并停止主机运动→用04:10读当前1字节→只替换patch涉及的位→04:0F写→等待ACK。整个“读+写”共用一个timeout预算，当前实现在先行中位停止之后开始该事务预算。未指定的位保留；但customFollow当前raw>15时拒写，不能自行放宽。

### 6.4 三轴档位位字段

| 域 | 参数 | index十进制（hex） |
|---|---|---|
| follow | speed | 65 (`41`) |
| follow | acceleration | 71 (`47`) |
| follow | deadZone | 66 (`42`) |
| rc | speed | 67 (`43`) |
| rc | deadZone | 68 (`44`) |
| rc | smoothing | 69 (`45`) |

size均1。pitch占bits2..3，roll占4..5，yaw占6..7；每轴custom=0、low=1、middle=2、high=3。bits0..1未知，读写保留。setter可只改一个或多个轴，仍采用6.3的先读后改写和总期限，不自动改下面的数值。

### 6.5 普通跟随/RC数值

下表每组三个index固定顺序**pitch、roll、yaw**；数值无符号小端，范围是当前命名setter允许范围，不是所有固件安全范围。读取超范围值仍返回rawValue和`withinSourceRange=false`。

| 域 | parameter | pitch | roll | yaw | size | 写范围 |
|---|---|---:|---:|---:|---:|---|
| follow | speed | 3 | 12 | 2 | 2 | 1..100 |
| follow | acceleration | 15 | 16 | 14 | 2 | 1..100 |
| follow | deadZone | 5 | 13 | 4 | 2 | 0..100 |
| rc | speed | 42 | 43 | 41 | 2 | 0..100 |
| rc | deadZone | 27 | 40 | 26 | 1 | 0..100 |
| rc | smoothing | 9 | 39 | 8 | 2 | 0..30 |

getter默认每个域9项，顺序按表的parameter组再pitch/roll/yaw；按axis/parameter过滤时保持此顺序。setter必须明确axis和parameter，每次只写一项：例如follow pitch acceleration=1：`0F 02 01 00`。当前实机曾读出加速度0，但SDK不允许写0，不能因为原值是0就绕过范围检查。

### 6.6 独立输入源配置

| parameter | pitch index | roll index | yaw index | size | 写范围 |
|---|---:|---:|---:|---:|---|
| speed | 80 | 79 | 81 | 2 | 0..100 |
| smoothing | 77 | 76 | 78 | 2 | 0..30 |

getter在选中数值的index前加72，先返回实际inputSourceRaw；默认顺序speed三轴、smoothing三轴。setter必须调用者显式提供`inputSource:2`，且每次发送：

```text
48 01 02 | selectedIndex 02 valueLow valueHigh
```

例如Pitch speed50：`48 01 02 50 02 32 00`。这是同时设置输入源和数值，不能当作普通follow或RC数值写，也不自动恢复原输入源。

## 7. 专用电机参数04:32/31

这是独立命令命名空间；下面的index0不是普通userProfile0，index3也不是普通follow pitch speed3。

| parameter | pitch | roll | yaw | size | 写范围 |
|---|---:|---:|---:|---:|---|
| stiffness | 0 | 1 | 2 | 1 | 5..100 |
| strength | 3 | 4 | 5 | 1 | 1..100 |
| gyroFiltering | 6 | 7 | 8 | 1 | 0..100 |
| preControl | 9 | 10 | 11 | 1 | 0..100 |

04:32请求仅1个index字节，ACK按6.1读取，宽度固定1。04:31写`index 01 value`，同命令ACK。

**必须逐项读。** 原设备多index电机请求不能可靠返回完整结果，现实现已改为循环单项。默认12项、按轴4项、按parameter3项、单项1项。顺序按上表逐行pitch/roll/yaw，过滤不改顺序。

单项返回真实响应加`readMode:'single'`和1个values元素；多项占一个操作槽，整个循环共用timeout，成功后返回`readMode:'sequential',atomic:false,replies,parameters,values`；每个replies保留真实单项响应。多项顶层不合成message/statusCode/ACK，不在失败或取消后返回半份成功结果，不继续发剩余请求。多项读取会停止正在运行的主机速度流；Node/Python单项有限查询可与其他有限查询并行。

## 8. 调参、水平校准、微调

### 8.1 电机自动调参04:6A与04:6E

`sendAutoTuneRequest({start:true|false})`发`00 01 01`或`00 01 00`，flags00，不请求ACK；返回sent=true、acknowledged=false。不能把“写入成功”改成“调参已完成”。

推送04:6E的payload本身就是记录序列：`tag:u8,size:u8,value[size]`。非空体第一个tag只能0或1，size不得>127，不能越界；tag0的size至少2，value[0]=状态，value[1]=进度。多个tag0以后者为当前值；未知记录和完整bodyHex保留。

状态：0 UnStart、1 Processing、2 Complete、3 Failure、255 UnKnown，其他state=null。进度rawPercent保留0..255，只有≤100才给percent，否则percent=null。没有tag0的推送不更新缓存；坏帧不发布部分结果。不要套旧`percent+bool`格式。

实测Complete100后设备可能显示完成提示，需要用户手动确认。false停止请求可使运行结束，但设备仍可能报告Complete；不制造“已回滚参数”或独立abort原因。通用stop不是此false请求。

### 8.2 水平校准04:08与04:30

只开放`sendComponentCalibrationRequest({sourcePart:'AUTO'})`，请求payload=`00`。不能据响应枚举开放GYRO、HALL等其他启动值。

事务：先中位停止→04:10读取普通参数35/size1→若raw bit0=1（电机禁用）报MOTOR_DISABLED且不发04:08→否则发AUTO00并等ACK。前置读取和ACK共用timeout预算，默认3000ms、允许>0..60000。

04:08 ACK原始payload：`ccode | part | status | tail`。不足2个business字节时calibration=null、businessComplete=false；不补默认状态。这里businessComplete只表示字段足够，不代表校准完成。

part源名称依序0..9：AUTO、JOINT_ANGLE、HALL_LINEAR、JOINT_ANGLE_CAMERA、JOINT_ANGLE_FIXTURE、GYRO、ACCELERATION、COMPASS、IMU_AND_SENSOR、SHOCK_PLATE；未知源回退字符串AUTO但known=false。status为0 FAIL、1 SUCCESS、2 PROCESSING；未知回退字符串PROCESSING但known=false。回退字符串不是确认状态，需同时看known与raw。保留part是否等于请求0及尾部。

实际水平校准进度走04:30推送：`rawProgress:u8,rawStatus:u8,tail`，至少2字节。**状态是0 COMPLETE、1 PROCESSING、3 FAIL、9 OTHER**；未知rawStatus→字符串OTHER且known=false。进度原样保留0..255，不钳到100、不从状态合成进度。该推送与6E调参缓存独立，不完成待处理查询/运动，不能凭推送序号猜测与某次启动关联。设备完成提示仍需手动确认。

### 8.3 手动微调04:07

只允许pitch和roll；axisCode：**roll=0，pitch=2**，不是枚举序号。adjustmentDegrees是有限−2..2，编码：

```text
tenths = trunc(float32(float32(adjustmentDegrees) * 10))
payload = [tenths & 0xFF, axisCode]
```

例如Pitch+2°=`14 02`、Pitch−2°=`EC 02`、Roll+1°=`0A 00`。不是四舍五入，要保留两次float32窄化再向0截断。先停止、独占至ACK。不能保证数值是绝对偏移还是增量，也不能一般性保证反向请求恢复原偏移。

## 9. 程序状态单次请求与四类保留推送

### 9.1 单次请求04:6B

program命名：track→`62`，timelapse→`37`，panorama→`63`。payload=`00 02 01 programId`，其中02是RequestSinglePush。只解析关联ACK的ccode/bodyHex；body不透明，不拿旧programStatus缓存充当这次查询响应，也不自动等某条推送。

这不是启动轨迹/延时/全景的命令。type0/1的连续订阅发送入口已移除，不应顺手恢复；固件程序执行仍未开放。

### 9.2 程序推送04:38、64、6B

共同要求：sender04、receiver02、set04、flags & 0x87 == 0。保留rawbody、记录原顺序、重复/未知字段；每次通知是独立快照，不合并旧单例字段。

| id | 最短体 | 内容 |
|---|---:|---|
| `38` | 4 | byte0 rawFlags；status=rawFlags&3；takingOrPreview=(rawFlags>>3)&1；unknownFlagBits=rawFlags&F4；byte1 finishedPoints、byte2 currentRoadPercent、byte3 totalRoadPercent |
| `64` | 5 | byte0 status；uint16LE@1 currentPictures；uint16LE@3 totalPictures |
| `6B` | 2 | byte0 rawSuccessByte；其后tag/length/value记录；0或1均sourceSuccess=true，其他false并返回空records而保留rawbody |

6B记录length必须<128，不可越界；已知tag最短长度：62和37为4，63为5。未知tag可0长度，保留rawTag、signedTag（>=128减256）、length、payloadHex。只要有一条坏记录，整条通知不更新缓存。

| tag | 解码value |
|---|---|
| `62` | status=v0, finishedPoints=v1, currentPercent=v2,totalPercent=v3 |
| `37` | rawFlags=v0,status=v0&7,recordingOrPreview=(v0>>3)&1,unknownFlagBits=v0&F0,finishedPoints=v1,currentRoadPercent=v2,totalRoadPercent=v3 |
| `63` | status=v0,currentPictures=u16LE@1,totalPictures=u16LE@3 |

38独立延时状态mask=3，而37记录mask=7；不要因名称相近统一为一个mask。counter/percent源值不随意钳制或补零，不把sourceSuccess=true当物理程序成功。

### 9.3 异常状态04:27

共同App推送信封、payload至少5字节。下表数值型字段取`(body[offset] >> shift) & mask`；布尔字段再转bool。所有字段为源码getter视图，不能未经型号/效果证据就触发自动关电机等控制。

| 名称 | offset | shift | mask | 类型 |
|---|---:|---:|---:|---|
| getFanDirection | 2 | 1 | 1 | 数值 |
| getGimbalDirectionWhenVertical | 2 | 5 | 1 | 数值 |
| getGimbalGravity | 3 | 1 | 3 | 数值 |
| getSleepMode | 4 | 0 | 1 | 数值 |
| getVerticalDirection | 2 | 2 | 1 | 数值 |
| isErrorRecentOrSelfie | 1 | 6 | 1 | bool |
| isErrorRecentWhenStartUp | 1 | 3 | 1 | bool |
| isInFlashlight | 2 | 3 | 1 | bool |
| isJointLockAfterStartup | 1 | 0 | 1 | bool |
| isJointLockWhenStartup | 1 | 1 | 1 | bool |
| isMotorProtected | 1 | 2 | 1 | bool |
| isPanoReady | 1 | 7 | 1 | bool |
| isPhoneOutGimbal | 3 | 0 | 1 | bool |
| isPitchLimitedInTracking | 3 | 6 | 1 | bool |
| isPitchLocked | 0 | 1 | 1 | bool |
| isPortrait | 2 | 4 | 1 | bool |
| isRollLocked | 0 | 0 | 1 | bool |
| isUpgrading | 1 | 4 | 1 | bool |
| isYawLimit | 1 | 5 | 1 | bool |
| isYawLimitedInTracking | 3 | 5 | 1 | bool |
| isYawLocked | 0 | 2 | 1 | bool |

额外`isGimbalLocked = isRollLocked OR isPitchLocked`，**不包括Yaw**。

### 9.4 发布规则

App来源仅保留四个缓存及事件：`calibrationStatus/calibration`、`sensorCalibrationStatus/sensorCalibration`、`abnormalStatus/abnormal`、`programStatus/program`。必须显式App profile；切换profile/断线清空。观察者抛异常或异步reject只上报onError，不能破坏解码、其他回调或内部缓存。Node通知路径依次为流重组→onNotification原始分片→逐帧pending关联→App状态分派→遥测缓存/waiter→onMessage完整帧副本→onTelemetry副本；CRC错误帧不会进入onMessage，但原始分片仍能被观察。结构化推送不自动发送ACK、续订或控制，不结束其他查询或运动。

已移除的教程、外部控制、外设、电池、手柄/摇杆、用户参数App状态只走原始消息，不创建空的“支持中”公开属性。调参/水平校准完成状态仍保留，不能因当轮未运行就误删。

## 10. CENTER只读信息00:32

明确`sourceVersion`，不自动协商或猜包：

| sourceVersion | 请求payload | business布局 |
|---|---|---|
| Ver1_0 | `01` | 最少18字节；SN从offset8取固定10字节 |
| Ver1_1 | `11` | 最少9字节；byte8为SN长度、SN从9开始 |
| Ver1_3 | `11` | 同长度字段布局 |
| Ver13 | `01` | **同长度字段布局，不是Ver1_0布局** |

TX02→E5,set00,id32,flags40；ACK E5→02，先ccode00再business。长度字段最多16且必须有足够数据；保留SN后的尾部。共同business字段：byte0 activeByte、bit0 sourceActiveBit、其他位unknownActiveBits；year=u16LE@1；month/day/hour/minute/second在3/4/5/6/7。不要把源activeBit当许可证/激活有效性的验收。

原始SN必须保留hex。为了兼容当前源字符串视图，只有ASCII数字/大小写字母直接转字符；其余字节按signed8十进制文本连接（例如80→`-128`），**不是UTF-8解码**。日期不强行验证或时区转换。本机只实测Ver1_1，其他为源码布局与离线向量证据。没有激活写入、序列号写入或自动回退尝试。

## 11. 仍存在的其他型号研究区（单独配置）

要准确复刻当前项目，不能把仍存在的研究入口默认为已验收功能，也不能因删除了App候选状态就声称这些研究分支不存在。默认禁用，只有`experimental.useProfile('rs3'|'rs3mini')`才启用；与App profile互斥且切换时清空两边缓存，busy/pending期间拒绝切换。

### 11.1 原始查询

`query({kind:'version'|'controlStatus'|'type',timeoutMs=3000})`分别对应00:01、04:0B、04:1C，空payload，flags40，返回关联原始消息。本机收到过这三种响应；业务布局未因此验证。`position`查询已移除，必须在发包前拒绝；正常04:05反馈不受影响。`requestDegreeInfo`不要求研究profile，另走04:1E。

### 11.2 研究写入

- `setSleep(asleep:bool)`：04:0F，payload=`23 01 value`；rs3的value=0/1，rs3mini的value=10/11。只写后返回sent，不等待ACK；有源差异，未作本机控制验收。
- `absolute({pan?,roll?,tilt?,parameterByte,observeMs=3000})`：仅rs3、属于上层实验封装。04:14数据体8字节，pan/roll/tilt分别int16LE@0/2/4，角度范围±180，编码JavaScript round(angle*10)。byte6初值01，未给pan/roll/tilt分别OR02/04/08；至少一轴；byte7必须调用者给0..255，不猜其单位。先stop→发一帧→观察等待→stop收尾，不代表到位。
- `rateFor({pan=0,roll=0,tilt=0,durationMs})`：仅rs3。04:0C体7字节，三个int16LE同顺序，输入有限±360并round(rate*10)，byte6=80；循环默认15Hz，结束先发相同三轴0、byte6=00的release，再三帧普通04:01中位。durationMs需明确且0..60000。
- 上述observe/duration不能解释为固件路径时间，也不能拿来开放新的当前App命令。停止/失败/取消不自动恢复旧设置或重放动作。

### 11.3 历史研究接收视图

此分支只在明确研究profile下发布`onExperimentalStatus`，并按kind存独立status字典；不混进四类App状态或常规姿态。共同receiver02、flags低3位为0、保存profile/rawpayload/deviceVerified=false。

| sender,set:id | 条件与布局 |
|---|---|
| 04,04:10 | ACK且非空；byte0返回码；从1循环index；index>=128解释signed错误码单项；其他index后size必须1/2/4/8再取raw值；只用于旧来源，不能替代第6节上下文协议 |
| 04,04:0F | ACK且仅1字节，得到user-parameter-ack/statusCode |
| 04,04:27 | 恰5字节，前4全0且byte4≤1，得到sleep/asleep |
| 04,04:0F | 恰4字节`00 23 01 value`，值须符合所选rs3/rs3mini，得到sleep/asleep=value&1 |
| 04,04:30 | 恰2字节，byte0≤100且byte1≤1，旧percent+bool视图；不得用于App当前Sensor状态枚举 |
| E5,0D:02 | 至少17字节；int32LE@1/5/9/13四个rawFields；仅rs3mini且恰21字节、byte20≤100时给候选batteryPercent，其他null |
| E5,04:66 | 至少1字节，byte0 header；从1读tag,size,value，size不得0且不可越界，值只保留hex不命名物理轴 |

这些旧来源分支中的原始候选不是0.7.39移除的App来源公开缓存，不可重新以旧入口别名“恢复支持”。

## 12. SDK事务、写队列、错误与生命周期

### 12.1 单一写队列与操作槽

所有命令共用一条串行写链。每个DUML帧的所有20字节分片发完才允许下一帧；不能让停止包插进当前帧中间。停止取消尚未开始的旧运动帧（epoch+signal），已开始的帧只检查会话是否仍有效，尽量完整写完，再停止。某次写失败应令会话失效、取消waiter和运动、执行有界清理，并在启用重连时安排重连。

Node/Python有限查询使用pending表，可与其他有限查询并行；参数写入、维护请求、速度切换、主机运动和多项电机读取拥有单一操作槽，冲突报BUSY，不排队偷偷晚执行。开始非setVelocity独占操作前若有非零速度流，先停止。所有命名写入也显式先中位停止。调用参数要先验证和快照，再占槽/发停止帧；无效参数不能造成设备动作。

操作执行器默认stopAfter=true，成功或异常都在finally调用内部停止；moveTo/moveFor/轨迹/路点/研究absolute/rate走此收尾。setVelocity、命名写入/维护、多项电机读取等使用stopAfter=false，正常结束不额外停止，但异常仍停止。setVelocity成功后释放操作槽，非零速度流可继续运行；不能把“操作槽空闲”当作“设备没有速度流”。

**内部停止与公开stop必须分开。** 内部`_stop`只终止速度流、递增epoch并发送中位，不取消当前操作本身；公开stop先abort当前操作，再调用内部停止并等其收尾。setter/校准的事务体内要用内部停止，不能用会取消自己的公开stop。并发停止共享stopPromise，operation.haltPromise复用同一次停止结果，避免取消过程中重复清理或自等待死锁。

```text
run(kind, body, stopAfter=true):
  检查ready/冲突，创建独占operation及cancel signal
  若非setVelocity且原有速度流活跃：await stopInternal()
  执行body(operation)，执行后再检查cancel signal
  finally:
    若stopAfter或发生错误：await (已有haltPromise 或 stopInternal())
    释放operation，并兑现operation.done
  保留原始错误；高层运动取消映射MOVE_CANCELLED
publicStop():
  abort当前operation；请求/复用haltPromise=stopInternal()
  等停止完成，再等operation.done；传播真实停止错误
```

自动前置停流和事务体自身显式内部停止都可能执行；已经完成后再次调用内部停止会再次发送三帧。完整会话的中位帧数量受调用路径影响，不能仅凭第16节单帧向量推断所有前后导步骤。

Node/Python `stop()`取消操作signal，发送停止并等当前operation收尾。高层moveTo/moveFor/轨迹/路点等取消统一MOVE_CANCELLED；设备设置/查询保留对应错误码。有限查询若未绑定运动signal，不因为stop或界面失焦自动取消；断线必取消。close/disconnect取消连接尝试，迟到发现/连接/订阅结果只能清理，不能重新发布ready。

Node/Python常用查询timeout默认3000ms，正数且≤60000。设备写I/O还有自己的3000ms期限。bitfield读改写及组件校准预算从先行stop之后计算；电机多项总预算从进入多项读取body开始。不要在每个子请求重置完整预算。清理和三帧停止可能使最终Promise返回晚于事务预算；预算不是“函数绝不超过此墙钟时间”的保证。超时若发生在一帧已经开始写出之后，设备仍可能收到完整请求甚至已经执行；不能自动重试写入/维护，也不能把超时解释成“设备未执行”。

原生macOS区别：当前原生App查询均独占且先发中位帧，15Hz timer/tick在主runloop工作，写出队列遵从canSendWriteWithoutResponse；先行stop结束后启动事务期限；不能声称与Node并发/停止前导完全相同。协议payload/响应规则相同。Python同时提供对应camelCase与snake_case别名；别名必须转同一个实现，不建第二连接。

### 12.2 断线与重连

失去会话立即：ready=false→解绑通知/断开监听→清空解析缓存、四类App缓存、研究缓存、最新遥测、速度→motionEpoch递增→取消stream/operation/query/waiter→通知onDisconnect。重连不重发旧运动、写入、订阅、校准请求。再次连接成功速度保持0。

Node自动重连默认关闭，显式`enableAutoReconnect`默认maxAttempts5、initialDelay500ms、maxDelay10000ms、backoff2、每次timeout10000ms、directTimeout5000ms。指数退避、延迟封顶；先排空旧会话操作与清理。状态disabled/idle/waiting/connecting/restored/exhausted，携带attempt。手动disconnect/close或disableAutoReconnect会取消自动重试；Node/Python的close后实例不可再connect；原生提供disconnect，窗口销毁/应用退出时调用，不照搬不存在的同名close选择器。Python保持对应显式策略；原生现有autoReconnectEnabled按其5次有界重试实现。

### 12.3 错误类别与结果保真

| 错误 | 使用处 |
|---|---|
| INVALID_ARGUMENT / TypeError / RangeError | 参数、命名枚举、数值范围、无效输入；不发包 |
| 原生RS4MINI_PROFILE_REQUIRED / Node TypeError | 未明确选择所需来源profile |
| RS4MINI_BUSY | 互斥冲突、切来源时有事务、pending超过64 |
| RS4MINI_DISCONNECTED | 未连接/会话失效/断线取消 |
| RS4MINI_CONNECT_TIMEOUT / CONNECT_CANCELLED / BLUETOOTH_UNAVAILABLE | 连接期限、取消、无权限/不支持 |
| RS4MINI_IO_TIMEOUT | 有界GATT写或清理超时 |
| RS4MINI_RESPONSE_TIMEOUT | 未收到关联响应、事务总预算耗尽 |
| RS4MINI_PROTOCOL_ERROR | 响应结构、ccode缺失、参数上下文不匹配 |
| RS4MINI_DEVICE_ERROR | 非零ccode；附原始response与statusCode |
| RS4MINI_MOTOR_DISABLED | AUTO校准前置检查不通过 |
| RS4MINI_UNSUPPORTED_VALUE | bitfield当前值超源setter范围，拒写 |
| RS4MINI_TELEMETRY_TIMEOUT | 等新姿态/关节超时 |
| RS4MINI_OPERATION_CANCELLED / MOVE_CANCELLED | 设备层操作/高层运动取消 |
| RS4MINI_MOVE_TIMEOUT / TRAJECTORY_OVERRUN / HOME_UNSET / ORIENTATION_INVALID | 见主机算法 |

保留raw message/bodyHex/headerByte/未知位；`deviceVerified:false`等源码保守标志是当前结果对象契约，即使另有实机验收记录，也不在解析器里随意统一改true。`acknowledged`、`sent`、`physicalCompletionVerified`是不同维度。

### 12.4 结果对象的字段约定

语言对象名可以按目标语言习惯包装，但对外兼容当前Node API时保留这些字段及null/false含义：

```text
DumlMessage = {raw:bytes,length,sender,receiver,sequence,flags,commandSet,commandId,payload:bytes}
AppCommandReply = {profile:'ronin-2.2.2',deviceVerified:false,physicalCompletionVerified:false,
                   statusCode:0,acknowledged:true,bodyHex,message:复制的DumlMessage}
AppParameterReply = AppCommandReply + {parameters:[{index,size,headerByte,rawHex},...]}
AttitudeReading = {pitch,roll,yaw,unit:'deg',wrap:180,raw:{pitch,roll,yaw},timestamp}
JointAnglesReading = {pitch,roll,yaw,unit:'deg',raw:{pitch,roll,yaw},timestamp}
```

04:05完整事件另有kind='gimbal-telemetry'、verified=true（现有已用布局标志，不证明所有固件）、兼容平面pitch/roll/yaw/raw取attitude、attitude子对象、jointAngles或null、orientationQuaternion或null、辅助字段、payloadHex、sequence、timestamp。子对象的时间放在外层事件；getter返回所选子对象副本加timestamp。orientationQuaternion={components:[4个float],norm,componentOrder:'unverified'}。

| 命名结果 | 基础对象之外的字段 |
|---|---|
| 灵敏度读取/写入 | 读取rawValue/mode；写入requestedMode |
| bitfield读取/写入 | 读settings/rawValue/unknownBits；写previousRawValue/requestedRawValue/requestedSettings |
| 普通numeric读 | values逐项含参数记录字段+axis/parameter/rawValue/withinSourceRange，activePresetVerified=false |
| 普通numeric写 | axis/parameter/requestedValue，activePresetVerified=false |
| standalone读/写 | 读inputSourceRaw、values与activePresetVerified=false；写axis/parameter/requestedValue/requestedInputSource=2与activePresetVerified=false |
| 电机读/写 | 读values及第7节readMode规则；写axis/parameter/requestedValue，不额外声称预设生效 |
| axisMode读/写 | 读rawValue/sourceModeValue/sourceMode/unknownBits、modelLayoutVerified=false、activePresetVerified=false；写requestedSourceMode/requestedRawValue、activePresetVerified=false、otherBitsPreservationVerified=false、persistenceVerified=false |
| smoothTrack读/写 | 读values每项含axis/rawValue/withinSourceRange/sourceEnabled/enabled和参数记录、modelLayoutVerified=false、activePresetVerified=false；写requestedAxes、activePresetVerified=false、atomicApplicationVerified=false、persistenceVerified=false |
| userProfile/workMode读 | parameter、rawValue、withinSourceRange及sourceUiName或sourceMode；modelLayoutVerified/activePresetVerified=false |
| userProfile/workMode写 | parameter、requestedRawValue及requestedSourceProfileValue或requestedSourceMode；activePresetVerified/persistenceVerified=false |
| 微调 | axis/requestedAdjustmentDegrees/encodedTenths/nominalAdjustmentDegrees/stabilizationStateVerified=false |
| AUTO ACK | requestedSourcePart='AUTO'、motorPreflightRawValue、motorPreflightEnabled、businessComplete、calibration或null、responsePartMatchesRequested；modelLayoutVerified/motorStatePhysicalVerified/businessRequestAssociationVerified/firmwareAbortVerified=false |
| 单次程序请求ACK | requestedProgram/requestedProgramCommandId/requestType='RequestSinglePush'；freshStatusVerified/programCorrelationVerified/modelLayoutVerified=false |
| CENTER ACK | 第10节字段加sourceVersion、receiverByte=229、sourceGetRequestByte；dateValidityVerified/actualSessionVersionVerified/activationValidityVerified/modelLayoutVerified/deviceVerified/physicalCompletionVerified=false |

自动调参的sent结果独立于AppCommandReply：{profile,sent:true,requestedStart,acknowledgementRequested:false,acknowledged:false,deviceVerified:false,physicalCompletionVerified:false}。研究写入返回{sent:true,deviceVerified:false,physicalCompletionVerified:false}。原始查询直接返回DumlMessage；recenter/stop/速度设置原接口无业务ACK结果，不伪造成功字段。

四类App事件都带kind/profile/timestamp及各自第8、9节字段；calibration带deviceVerified=false/physicalCompletionVerified=false；sensorCalibration另带commandId=48、modelLayoutVerified=false、progressUnitVerified=false、requestAssociationVerified=false；program另带commandId、modelLayoutVerified=false、programCorrelationVerified=false；abnormal另带modelLayoutVerified=false。各保留bodyHex，sensor还保留trailingHex。内嵌参考代码只返回编解码的确定字段，时间与通用包装按此节加上，不用运行时机器时间作黄金向量断言。

## 13. 现有主机组合层复刻算法

只复刻现有功能，不因文档新增高级功能。所有函数仍共享第12节同一连接/队列/操作槽。

### 13.1 定时速度与定位

- `setVelocityDeg`用panFullScale37.5、tiltFullScale27.5、rollFullScale30作默认除数，再调用归一化setVelocity；这些是主机换算尺度，不是固件保证的度/秒。调用者可覆盖正尺度。
- `moveFor`验证durationMs有限且≥0，发送给定速度→可取消等待durationMs→finally停止。duration0仍按同一生命周期处理。
- `moveTo`只接受pan/tilt/roll中至少一轴，目标每轴−180..180；默认toleranceDeg1、总timeout30000、telemetryTimeout3000、gain0.02、minSpeed0.05、maxSpeed0.18，速度需0≤min≤max≤1，其余正数。先等新关节帧；每个循环检查总期限。

```text
panError = ((targetPan - jointYaw + 540) mod 360) - 180
tiltError = targetTilt - jointPitch
rollError = targetRoll - jointRoll
未指定轴error=0
若所有 |error| <= tolerance：返回target/current/error/elapsed，finally停止
speed(e) = 0（容差内），否则 sign(e)*min(maxSpeed,max(minSpeed,abs(e)*gain))
发setVelocity(pan=speed(panError), tilt=-speed(tiltError), roll=speed(rollError))
等待下一帧新关节，再循环
```

Pan处理环绕，Tilt/Roll用直接差，不能擅自统一。负数mod的语言差异需处理；合法输入范围时上式+540在本项目满足正余数。总超时MOVE_TIMEOUT，等反馈超时TELEMETRY_TIMEOUT；不拿旧帧无限继续运动。不把回中零点用作定位绝对参照。

### 13.2 轨迹、路点、保存位置

`runTrajectory`是速度关键帧，不是固件轨迹上传：至少2点、首timeMs=0、严格递增且≤2^31−1，未指定轴补0，归一化速度−1..1。插值linear比例r、smoothstep比例r²(3−2r)、step取前点（跨到后点时取后点）。默认maxLagMs500。用单调时钟按1/rateHz调度；写入迟到跳过过时调度点，不突发补发；延迟或单次写耗时>maxLagMs报TRAJECTORY_OVERRUN并停止。duration为最后timeMs，到达后停止，不强行再发最后关键帧速度。返回sentFrames/skippedFrames/elapsed；progress在结束后清空。

`moveThrough`逐个执行同一moveTo内部循环；每点完成后先stop，再holdMs（默认0，0..2^31−1，可取消）。整个路点任务占一个操作槽，不递归抢槽。任意失败不执行后续点。

`captureHome`保存当前关节映射pan=Yaw、tilt=Pitch、roll=Roll，以及timestamp/deviceId，返回副本；`moveHome`必须同一deviceId，选非空不重复轴集合，默认三轴，通过moveTo返回所选轴，不是硬件原生home命令。

### 13.3 显式四元数数学

必须调用者明确`componentOrder='wxyz'|'xyzw'`及可选conjugate，默认不猜设备顺序。读取四个finite分量；norm>1e−12；getOrientation额外要求`abs(norm−1)≤normTolerance`（默认0.1），否则ORIENTATION_INVALID。按顺序重排归一化w,x,y,z，conjugate时x/y/z取负；采用右手intrinsic ZYX：

```text
roll  = atan2(2(wx+yz), 1-2(x²+y²)) * 180/pi
pitch = asin(clamp(2(wy-zx), -1, 1)) * 180/pi
yaw   = atan2(2(wz+xy), 1-2(y²+z²)) * 180/pi
```

结果注明deviceConventionVerified=false，不把此数学选择当设备物理参考系。

原生RSPositionLoop采用相同误差方向与默认常数，但当前公开moveTo字典只接收目标轴，不开放Node/Python的自定义gain/速度/容差/timeout选项；由15Hz tick检查30秒总期限、3秒反馈期限。不要声称三端参数配置能力完全一样。

## 14. 应用接口与原生界面要求

设备层公开：连接/断开/关闭、自动重连开关、setVelocity、stop、recenter、requestDegreeInfo、getAttitude/getJointAngles；状态connected/activeOperation/velocity/latestTelemetry/reconnectState，回调onNotification/onMessage/onTelemetry/onDisconnect/onError/onReconnect/onAppStatus/onExperimentalStatus。

AppCommands公开32个命名操作加useProfile，具体映射如下。所有读取options可有timeoutMs；写入同理（sendAutoTuneRequest只有start）。

| 方法组 | 参数 / 对应章节 |
|---|---|
| get/setFollowSensitivity | mode0/1；6.2 |
| get/setCustomFollowSettings | enabled/pitch/roll/yaw bool patch；6.3 |
| get/setMotorSettings | enabled/forbidSelfie/forbidVertical/roll360 bool patch；6.3 |
| get/setFollowSettings | parameter=speed/acceleration/deadZone，轴档位patch；6.4 |
| get/setRcSettings | parameter=speed/deadZone/smoothing，轴档位patch；6.4 |
| get/setFollowTuning | axis、parameter、写value；6.5 |
| get/setRcTuning | axis、parameter、写value；6.5 |
| get/setStandaloneTuning | axis、parameter、写inputSource2/value；6.6 |
| get/setMotorTuning | axis、parameter、写value；7 |
| getAxisMode/sendAxisModeRequest | sourceMode；6.2 |
| getSmoothTrackAxes/sendSmoothTrackAxesRequest | 读axis、写axes bool字典；6.2 |
| getUserProfile/sendUserProfileRequest | sourceProfileValue；6.2 |
| getWorkMode/sendWorkModeRequest | sourceMode；6.2 |
| readParameters | 显式index/size上下文；6.1 |
| sendFineTuneRequest | axis和adjustmentDegrees；8.3 |
| sendAutoTuneRequest | start bool；8.1 |
| sendComponentCalibrationRequest | sourcePart:'AUTO'；8.2 |
| sendProgramStatusRequest | program；9.1 |
| getCenterActivationInfo | sourceVersion；10 |

App profile状态与四个缓存可只读获取。高层增加第13节方法和moveToActive/trajectoryProgress/home。附录API清单从当前原型枚举生成，可用来检查遗漏；Python提供相应snake别名，原生对应selector/字典参数。

macOS GUI最小复刻：左侧连接/断开、停止、三轴按住速度、回中和当前反馈；设备面板32个命名操作，根据上表字段渲染枚举/布尔/数值表单；只通过单一RSGimbal调用SDK。JSON显示原始响应与证据标志，状态快照仅calibration/sensorCalibration/abnormal/program四类，缺失显示null，不能显示0或成功。异步操作结束后恢复idle按钮状态；失败/取消同样释放，不依赖收到某条推送才能解锁。研究JSON入口独立且要求显式profile；不得从普通表单拼任意帧。设备结果弹窗仍由用户在稳定器屏幕确认。

Web端已移除，不创建浏览器蓝牙实现。当前复刻不包含相机拍摄、视觉追踪、固件更新、厂商App执行或APK解保护工具；运行SDK不依赖它们。

### 14.1 可独立建立的项目骨架与运行环境

```text
node/   package.json、src/device、protocol、telemetry、app_commands、controller，test/
python/ pyproject.toml、rs4mini_sdk/同职责模块，tests/
macos/  Foundation/CoreBluetooth设备层、纯协议核心、主机算法、AppKit面板
```

Node根入口还导出crc8/crc16/frame/velocityFrame/stopFrame/recenterFrame、parseDumlFrame/DumlStreamDecoder/decodeGimbalTelemetry、orientationFromComponents。兼容名decodeGimbalPositionCandidate只是decodeGimbalTelemetry的别名，解析04:05；它不是已移除的04:02主动查询。

Node包名rs4mini-sdk，ESM；依赖`@stoprocent/noble ^2.8.0`，导出根入口RS4Mini、`./device`入口BleDevice、`./protocol`纯编码函数。默认导入/离线测试不启动扫描或连接；通过适配器注入假设备。Python包名rs4mini-sdk，模块rs4mini_sdk，setuptools>=68构建，依赖`bleak>=0.22,<2`；根入口RS4Mini，设备层可独立导入，保留camelCase/snake_case别名。当前锁定Noble2.8.0；本机已使用的依赖组合为Python3.8+Bleak0.22.3、Python3.12+Bleak1.1.1，这也是缓存UUID桥需要兼容rssi构造参数差异的原因。本轮只做文档与离线检查，不把依赖已安装当新增实机验收。序列化按JS半值规则及float32规则实现，不能用语言默认round替代。

macOS目标12.0+，xcrun clang + ARC/modules；设备层仅链接Foundation/CoreBluetooth，高层增加纯数学/组合模块，GUI再链接AppKit。Info.plist：CFBundleIdentifier=`local.codex.rs4minicontrol`、CFBundleExecutable=`RS4MiniControl`、CFBundleShortVersionString=`0.3.40`、CFBundleVersion=`43`、NSBluetoothAlwaysUsageDescription为用户可读说明；本地构建可ad-hoc签名，再codesign --verify --deep --strict。使用中央管理器的主runloop，异步完成回调不要阻塞UI线程。

原生App命令以completion(result,error)异步返回，字典参数键沿用第14节；get方法常见选择器为`get…WithTimeoutMs:completion:`或`get…:timeoutMs:completion:`，set/send为`…:timeoutMs:completion:`。App profile用`useAppProfile:`；自动调参为`sendAutoTuneRequest:completion:`。基础速度为`drivePan:tilt:roll:`，遥测由telemetryHandler传递，原始帧由messageHandler传递；ready/busy等只读，不虚构与Node完全相同的getter选择器。可独立复刻所需的完整公开头如下（这是接口，不包含内部实现）：

<!-- NATIVE_PUBLIC_BEGIN -->
```objc
#import <Foundation/Foundation.h>
#import <CoreBluetooth/CoreBluetooth.h>
typedef void (^StatusHandler)(NSString *text, BOOL ready);
typedef void (^TelemetryHandler)(NSDictionary *sample);
typedef void (^RSAppCompletion)(NSDictionary *result, NSError *error);
// Device layer: independent of RSGimbal and composed motion.
@interface RSBleDevice : NSObject <CBCentralManagerDelegate, CBPeripheralDelegate>
@property(nonatomic, readonly, copy) NSDictionary *appSensorCalibrationStatus;
@property(nonatomic, readonly, copy) NSDictionary *appProgramStatus;
@property(nonatomic, readonly, copy) NSDictionary *appAbnormalStatus;
@property(nonatomic, readonly) BOOL ready;
@property(nonatomic, readonly) BOOL connecting;
@property(nonatomic, readonly) BOOL busy;
@property(nonatomic, copy) TelemetryHandler telemetryHandler;
@property(nonatomic) BOOL autoReconnectEnabled;
@property(nonatomic, readonly) NSUInteger reconnectAttempt;
@property(nonatomic, readonly) NSDictionary *experimentalStatus;
@property(nonatomic, copy) TelemetryHandler experimentalStatusHandler;
- (instancetype)initWithStatus:(StatusHandler)handler;
- (instancetype)initWithStatus:(StatusHandler)handler central:(CBCentralManager *)central;
- (void)requestDegreeInfo;
@property(nonatomic, readonly, copy) NSString *appProfile;
- (void)sendComponentCalibrationRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)sendFineTuneRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)getUserProfileWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)getWorkModeWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)sendUserProfileRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)sendWorkModeRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)getSmoothTrackAxes:(NSDictionary *)filters timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)sendSmoothTrackAxesRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)getAxisModeWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)sendAxisModeRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)getCenterActivationInfo:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (BOOL)useAppProfile:(NSString *)profile;
- (void)sendProgramStatusRequest:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)readAppParameters:(NSArray<NSDictionary *> *)parameters timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)getFollowSensitivityWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)setFollowSensitivity:(NSNumber *)mode timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)getFollowSettings:(NSString *)parameter timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)setFollowSettings:(NSString *)parameter settings:(NSDictionary *)settings timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)getRcSettings:(NSString *)parameter timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)setRcSettings:(NSString *)parameter settings:(NSDictionary *)settings timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)getCustomFollowSettingsWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)getMotorSettingsWithTimeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)setCustomFollowSettings:(NSDictionary *)settings timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)setMotorSettings:(NSDictionary *)settings timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
@property(nonatomic, readonly, copy) NSDictionary *appCalibrationStatus;
@property(nonatomic, copy) TelemetryHandler appStatusHandler;
- (void)sendAutoTuneRequest:(NSNumber *)start completion:(RSAppCompletion)completion;
- (void)getStandaloneTuning:(NSDictionary *)filters timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)setStandaloneTuning:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)getFollowTuning:(NSDictionary *)filters timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)setFollowTuning:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)getRcTuning:(NSDictionary *)filters timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)setRcTuning:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)getMotorTuning:(NSDictionary *)filters timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
- (void)setMotorTuning:(NSDictionary *)spec timeoutMs:(double)timeoutMs completion:(RSAppCompletion)completion;
@property(nonatomic, copy) TelemetryHandler messageHandler;
- (void)connect;
- (void)disconnect;
- (void)drivePan:(double)pan tilt:(double)tilt roll:(double)roll;
- (void)stop;
- (void)recenter;
@end

// Single application entry.
@interface RSGimbal : RSBleDevice
@property(nonatomic, readonly) NSDictionary *home;
- (void)moveTo:(NSDictionary *)targets;
- (void)runTrajectory:(NSArray *)keyframes interpolation:(NSString *)interpolation;
- (void)moveThrough:(NSArray *)waypoints;
- (void)captureHome;
- (void)moveHomeAxes:(NSArray<NSString *> *)axes;
- (NSDictionary *)orientationWithOrder:(NSString *)order conjugate:(BOOL)conjugate;
// Explicit other-model research profile in the command dictionary; never auto-enabled.
- (void)sendExperimentalCommand:(NSDictionary *)command;
@end
```
<!-- NATIVE_PUBLIC_END -->

## 15. 禁止误恢复的历史接口

以下仅用于识别旧文档/源码中的历史痕迹，不属于当前SDK收发白名单：

- 04:02位置查询；getHandleSettings、queryCalibrationStatus。
- sendAutoCalibrationRequest/getAutoCalibrationStatus（旧普通参数index36 system_calc）；sendBalanceTestRequest/getBalanceTestStatus（旧index37主动平衡测试）。重复无可见效果后移除，不能用名称替代已验收AUTO水平校准。
- 参数订阅、程序连续订阅、订阅键公开目录、手柄/摇杆写入、恢复设置发送；不恢复出厂、不发送激活写入。
- tutorialStatus、externalDeviceStatus、peripheralStatus、batteryStatus、handheldStickStatus、userParameterStatus及对应App事件；其纯函数/向量可能仍存于历史研究文件，不接运行时。
- 04:2C教程步骤、04:40旧平衡调整、固件轨迹/延时/全景执行、相机和未命名参数写入。知道命令号不等于允许发送。

底层原始消息仍允许观察未知帧；不可用未知帧生成已知结构化状态或自动控制。当前“常规验收通过”指记录过的现有功能/数值/负载；不涵盖所有数值组合、所有固件和所有机身姿态。

## 16. 离线参考代码和验收向量

下面的Python3.8+参考实现仅处理内存字节，不导入BLE库、不扫描、不连接设备。它是从上文规则独立编写的可执行复刻起点。为保持文档自包含，参数表和关键解码器也内置于代码。实际异步连接和操作协调按第2、12、13节实现。

<!-- REFERENCE_PYTHON_BEGIN -->
```python
import sys, json, math, struct

def need(ok, reason='invalid input'):
    if not ok: raise ValueError(reason)

def crc(data, seed, poly, mask):
    v = seed
    for b in data:
        v ^= b
        for _ in range(8): v = (v >> 1) ^ (poly if v & 1 else 0)
    return v & mask

def crc8(data): return crc(data, 0x77, 0x8c, 255)
def crc16(data): return crc(data, 0x3692, 0x8408, 65535)
def round_js(v): return math.floor(v + 0.5)
def f32(v): return struct.unpack('<f', struct.pack('<f', v))[0]
def integer(v): return isinstance(v, int) and not isinstance(v, bool)
def finite(v): return isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)

def frame(sequence, command_set, command_id, body=b'', flags=0, sender=2, receiver=4):
    n = len(body) + 13
    need(13 <= n <= 1023, 'frame length')
    p = bytearray(n)
    p[:3] = bytes((0x55, n & 255, 4 | ((n >> 8) & 3)))
    p[3] = crc8(p[:3]); p[4:6] = bytes((sender, receiver))
    struct.pack_into('<H', p, 6, sequence & 65535)
    p[8:11] = bytes((flags, command_set, command_id)); p[11:-2] = body
    struct.pack_into('<H', p, n - 2, crc16(p[:-2]))
    return bytes(p)

def parse(p):
    need(len(p) >= 13 and p[0] == 0x55, 'header')
    need((p[1] | ((p[2] & 3) << 8)) == len(p), 'length')
    need(crc8(p[:3]) == p[3] and crc16(p[:-2]) == struct.unpack_from('<H', p, len(p)-2)[0], 'CRC')
    return dict(rawHex=p.hex(), length=len(p), sender=p[4], receiver=p[5],
                sequence=struct.unpack_from('<H', p, 6)[0], flags=p[8],
                commandSet=p[9], commandId=p[10], payloadHex=p[11:-2].hex())

class Stream:
    def __init__(self, limit=8192):
        need(integer(limit) and limit >= 13)
        self.limit=limit; self.buffer=b''; self.discardedBytes=0; self.invalidFrames=0
    def feed(self, chunk):
        if not chunk: return []
        self.buffer += chunk
        if len(self.buffer) > self.limit:
            keep=max(0,self.buffer.rfind(b'\x55')); self.discardedBytes+=keep; self.buffer=self.buffer[keep:]
            if len(self.buffer)>self.limit:
                self.discardedBytes+=len(self.buffer); self.buffer=b''
        out=[]
        while self.buffer:
            start=self.buffer.find(b'\x55')
            if start<0:
                self.discardedBytes+=len(self.buffer); self.buffer=b''; break
            self.discardedBytes+=start; self.buffer=self.buffer[start:]
            if len(self.buffer)<4: break
            n=self.buffer[1] | ((self.buffer[2]&3)<<8)
            valid=13<=n<=1023 and crc8(self.buffer[:3])==self.buffer[3]
            if valid and len(self.buffer)<n: break
            if valid:
                try: out.append(parse(self.buffer[:n]))
                except ValueError: valid=False
            if valid: self.buffer=self.buffer[n:]
            else:
                self.invalidFrames+=1; self.discardedBytes+=1; self.buffer=self.buffer[1:]
        return out

AXES=['pitch','roll','yaw']
NUMERIC={
 'follow':[('speed',[3,12,2],2,1,100),('acceleration',[15,16,14],2,1,100),('deadZone',[5,13,4],2,0,100)],
 'rc':[('speed',[42,43,41],2,0,100),('deadZone',[27,40,26],1,0,100),('smoothing',[9,39,8],2,0,30)],
 'standalone':[('speed',[80,79,81],2,0,100),('smoothing',[77,76,78],2,0,30)],
 'motor':[(p,[3*g,3*g+1,3*g+2],1,m,100) for g,(p,m) in enumerate([('stiffness',5),('strength',1),('gyroFiltering',0),('preControl',0)])]
}
MODE_INDEX={'followSpeed':65,'followAcceleration':71,'followDeadZone':66,'rcSpeed':67,'rcDeadZone':68,'rcSmoothing':69}
MODE_NAMES=['custom','low','middle','high']
def selection(domain, axis=None, parameter=None):
    need(domain in NUMERIC)
    need(axis is None or axis in AXES)
    need(parameter is None or parameter in [x[0] for x in NUMERIC[domain]])
    return [dict(axis=a,parameter=p,index=ids[i],size=size,min=lo,max=hi)
            for p,ids,size,lo,hi in NUMERIC[domain] for i,a in enumerate(AXES)
            if (axis is None or a==axis) and (parameter is None or p==parameter)]
def context(rows):
    need(isinstance(rows,list) and 1<=len(rows)<=64)
    for r in rows:
        need(set(r)=={'index','size'} and integer(r['index']) and 0<=r['index']<=255
             and integer(r['size']) and r['size'] in (1,2,4,8))
    return rows

def payload(operation, **k):
    kind=operation
    if kind=='velocity':
        vals=[]
        for a in ('tilt','roll','pan'):
            v=float(k.get(a,0));need(math.isfinite(v));vals.append(1024+round_js(max(-1,min(1,v))*660))
        return struct.pack('<hhhhB',*(vals+[0,2]))
    if kind=='recenter': return bytes((254,1))
    if kind=='read': return bytes(r['index'] for r in context(k['parameters']))
    if kind=='sensitivity':
        v=k['mode'];need(integer(v) and v in (0,1));return bytes((150,1,v))
    if kind=='numeric':
        need(k.get('axis') in AXES and k.get('parameter') is not None)
        row=selection(k['domain'],k['axis'],k['parameter'])[0];v=k['value']
        need(integer(v) and row['min']<=v<=row['max'])
        out=bytes((row['index'],row['size']))+v.to_bytes(row['size'],'little')
        if k['domain']=='standalone':
            need(k.get('inputSource')==2 and integer(k['inputSource']));out=bytes((72,1,2))+out
        return out
    if kind=='settings':
        name=k['kind'];patch=k['patch'];raw=k['raw']
        modes=name in MODE_INDEX
        fields={'pitch':2,'roll':4,'yaw':6} if modes else ({'enabled':1,'pitch':2,'roll':4,'yaw':8} if name=='customFollow' else {'enabled':1,'forbidSelfie':16,'forbidVertical':32,'roll360':64})
        need(modes or name in ('customFollow','motor'));need(integer(raw) and 0<=raw<=(15 if name=='customFollow' else 255))
        need(isinstance(patch,dict) and patch and all(a in fields for a in patch))
        v=raw
        for a,x in patch.items():
            bit=fields[a]
            if modes:
                need(x in MODE_NAMES);v=(v & (255 ^ (3<<bit))) | (MODE_NAMES.index(x)<<bit)
            else:
                need(isinstance(x,bool));put=(not x) if name=='motor' and a=='enabled' else x
                v=(v|bit) if put else (v & (255^bit))
        return bytes((MODE_INDEX[name] if modes else (132 if name=='customFollow' else 35),1,v))
    if kind=='axis_mode':
        modes={'ThreeAxis':0,'TwoAxis':8,'Roll360':16,'ThreeDRoll360':24};need(k['sourceMode'] in modes)
        return bytes((34,1,modes[k['sourceMode']]))
    if kind=='smooth':
        patch=k['axes'];need(isinstance(patch,dict) and patch and all(a in ('yaw','pitch','roll') and isinstance(v,bool) for a,v in patch.items()))
        return bytes(b for a,i in [('yaw',17),('pitch',18),('roll',19)] if a in patch for b in (i,1,int(patch[a])))
    if kind=='user_profile':
        v=k['sourceProfileValue'];need(integer(v) and 0<=v<=5);return bytes((0,1,v))
    if kind=='work_mode':
        names=['Free','Flower','Fpv','Center'];need(k['sourceMode'] in names);return bytes((62,1,names.index(k['sourceMode'])))
    if kind=='fine':
        v=k['adjustmentDegrees'];need(k['axis'] in ('pitch','roll') and finite(v) and -2<=v<=2)
        return bytes((math.trunc(f32(f32(v)*10)) & 255,2 if k['axis']=='pitch' else 0))
    if kind=='autotune':
        need(isinstance(k['start'],bool));return bytes((0,1,int(k['start'])))
    if kind=='component':
        need(k['sourcePart']=='AUTO');return b'\0'
    if kind=='program':
        ids={'track':98,'timelapse':55,'panorama':99};need(k['program'] in ids);return bytes((0,2,1,ids[k['program']]))
    if kind=='center':
        versions={'Ver1_0':1,'Ver1_1':17,'Ver1_3':17,'Ver13':1};need(k['sourceVersion'] in versions);return bytes((versions[k['sourceVersion']],))
    if kind=='research_sleep':
        need(k['profile'] in ('rs3','rs3mini') and isinstance(k['asleep'],bool));return bytes((35,1,(16 if k['profile']=='rs3mini' else 0)|int(k['asleep'])))
    if kind=='research_absolute':
        body=bytearray(8);flag=1;supplied=0
        for a,offset,invalid in [('pan',0,2),('roll',2,4),('tilt',4,8)]:
            if a not in k:flag|=invalid
            else:
                need(finite(k[a]) and abs(k[a])<=180);struct.pack_into('<h',body,offset,round_js(k[a]*10));supplied+=1
        v=k['parameterByte'];need(supplied and integer(v) and 0<=v<=255);body[6:]=bytes((flag,v));return bytes(body)
    if kind=='research_rate':
        vals=[k.get(a,0) for a in ('pan','roll','tilt')];need(all(finite(v) and abs(v)<=360 for v in vals))
        release=k.get('release',False);need(isinstance(release,bool))
        return struct.pack('<hhhB',*[round_js(v*10) for v in vals],0 if release else 128)
    raise ValueError('unknown payload kind')

def parameters_reply(body, rows):
    context(rows);need(body and body[0]==0,'ccode');offset=1;out=[]
    for row in rows:
        i,size=row['index'],row['size'];need(offset+2+size<=len(body) and body[offset]==i,'context mismatch')
        out.append(dict(index=i,size=size,headerByte=body[offset+1],rawHex=body[offset+2:offset+2+size].hex()));offset+=2+size
    need(offset==len(body),'unconsumed bytes')
    return dict(bodyHex=body[1:].hex(),parameters=out)

def calibration(body):
    need(not body or body[0] in (0,1));offset=0;records=[];state=percent=None
    while offset<len(body):
        need(offset+2<=len(body));tag,size=body[offset:offset+2];offset+=2
        need(size<=127 and offset+size<=len(body) and (tag!=0 or size>=2))
        p=body[offset:offset+size];records.append(dict(tag=tag,size=size,rawHex=p.hex()))
        if tag==0:state,percent=p[:2]
        offset+=size
    return dict(records=records,rawState=state,state={0:'UnStart',1:'Processing',2:'Complete',3:'Failure',255:'UnKnown'}.get(state),rawPercent=percent,percent=percent if percent is not None and percent<=100 else None,bodyHex=body.hex())

def program_values(tag,p):
    if tag==98:return dict(status=p[0],finishedPoints=p[1],currentPercent=p[2],totalPercent=p[3])
    if tag==55:return dict(rawFlags=p[0],status=p[0]&7,recordingOrPreview=(p[0]>>3)&1,finishedPoints=p[1],currentRoadPercent=p[2],totalRoadPercent=p[3],unknownFlagBits=p[0]&240)
    if tag==99:return dict(status=p[0],currentPictures=int.from_bytes(p[1:3],'little'),totalPictures=int.from_bytes(p[3:5],'little'))
    return None
def program(body,command):
    need(command in (56,100,107) and len(body)>={56:4,100:5,107:2}[command])
    out=dict(commandId=command,bodyHex=body.hex(),format={56:'standalone-timelapse',100:'standalone-panorama',107:'program-records'}[command],sourceValues=None,rawSuccessByte=None,sourceSuccess=None,records=[])
    if command==56:
        out['sourceValues']=dict(rawFlags=body[0],status=body[0]&3,takingOrPreview=(body[0]>>3)&1,finishedPoints=body[1],currentRoadPercent=body[2],totalRoadPercent=body[3],unknownFlagBits=body[0]&244);return out
    if command==100:out['sourceValues']=program_values(99,body);return out
    out['rawSuccessByte']=body[0];out['sourceSuccess']=body[0] in (0,1)
    if not out['sourceSuccess']:return out
    offset=1
    while offset<len(body):
        need(offset+2<=len(body));tag,size=body[offset:offset+2];end=offset+2+size
        need(size<128 and end<=len(body) and size>={98:4,55:4,99:5}.get(tag,0))
        p=body[offset+2:end];out['records'].append(dict(rawTag=tag,sourceSignedTag=tag if tag<128 else tag-256,length=size,payloadHex=p.hex(),sourceValues=program_values(tag,p)));offset=end
    return out

ABNORMAL=[('getFanDirection',2,1,1,False),('getGimbalDirectionWhenVertical',2,5,1,False),('getGimbalGravity',3,1,3,False),('getSleepMode',4,0,1,False),('getVerticalDirection',2,2,1,False),('isErrorRecentOrSelfie',1,6,1,True),('isErrorRecentWhenStartUp',1,3,1,True),('isInFlashlight',2,3,1,True),('isJointLockAfterStartup',1,0,1,True),('isJointLockWhenStartup',1,1,1,True),('isMotorProtected',1,2,1,True),('isPanoReady',1,7,1,True),('isPhoneOutGimbal',3,0,1,True),('isPitchLimitedInTracking',3,6,1,True),('isPitchLocked',0,1,1,True),('isPortrait',2,4,1,True),('isRollLocked',0,0,1,True),('isUpgrading',1,4,1,True),('isYawLimit',1,5,1,True),('isYawLimitedInTracking',3,5,1,True),('isYawLocked',0,2,1,True)]
def abnormal(body):
    need(len(body)>=5)
    v={name:bool((body[o]>>s)&m) if boolean else (body[o]>>s)&m for name,o,s,m,boolean in ABNORMAL}
    v['isGimbalLocked']=v['isRollLocked'] or v['isPitchLocked'];return dict(bodyHex=body.hex(),sourceValues=v)

def sensor(body):
    need(len(body)>=2);names={0:'COMPLETE',1:'PROCESSING',3:'FAIL',9:'OTHER'}
    return dict(rawProgressValue=body[0],rawStatus=body[1],sourceStatus=names.get(body[1],'OTHER'),sourceStatusKnown=body[1] in names,bodyHex=body.hex(),trailingHex=body[2:].hex())

def component(body):
    need(body and body[0]==0,'ccode');b=body[1:];complete=len(b)>=2;c=None
    if complete:
        parts=['AUTO','JOINT_ANGLE','HALL_LINEAR','JOINT_ANGLE_CAMERA','JOINT_ANGLE_FIXTURE','GYRO','ACCELERATION','COMPASS','IMU_AND_SENSOR','SHOCK_PLATE'];states=['FAIL','SUCCESS','PROCESSING']
        c=dict(rawPart=b[0],sourcePart=parts[b[0]] if b[0]<10 else 'AUTO',sourcePartKnown=b[0]<10,rawStatus=b[1],sourceStatus=states[b[1]] if b[1]<3 else 'PROCESSING',sourceStatusKnown=b[1]<3,bodyHex=b.hex(),trailingHex=b[2:].hex())
    return dict(bodyHex=b.hex(),businessComplete=complete,calibration=c,responsePartMatchesRequested=b[0]==0 if complete else None)

def center(body,version):
    payload('center',sourceVersion=version);need(body and body[0]==0);b=body[1:];old=version=='Ver1_0';need(len(b)>=(18 if old else 9))
    offset=8 if old else 9;n=10 if old else b[8];need(n<=16 and len(b)>=offset+n);sn=b[offset:offset+n]
    text=''.join(chr(v) if 48<=v<=57 or 65<=v<=90 or 97<=v<=122 else str(v if v<128 else v-256) for v in sn)
    return dict(activeByte=b[0],sourceActiveBit=bool(b[0]&1),unknownActiveBits=b[0]&254,dateRaw=dict(year=int.from_bytes(b[1:3],'little'),month=b[3],day=b[4],hour=b[5],minute=b[6],second=b[7]),serialNumberRawHex=sn.hex(),sourceSerialNumber=text,serialNumberLength=n,trailingBodyHex=b[offset+n:].hex(),bodyHex=b.hex())

def telemetry(body):
    need(len(body)>=6)
    def i16(o):return struct.unpack_from('<h',body,o)[0]
    attitude={a:i16(o)/10 for a,o in [('pitch',0),('roll',2),('yaw',4)]}
    joints={a:i16(o)/scale for a,o,scale in [('pitch',20,10),('roll',22,10),('yaw',16,100)]} if len(body)>=24 else None
    components=[struct.unpack_from('<f',body,o)[0] for o in (24,28,32,36)] if len(body)>=40 else None
    aux=dict(modeFlags=body[6] if len(body)>=7 else None,rollAdjust=struct.unpack_from('<b',body,7)[0] if len(body)>=8 else None,yawAngle=i16(8)/10 if len(body)>=10 else None,limitFlags=body[10] if len(body)>=11 else None,stateFlags=body[11] if len(body)>=12 else None)
    return dict(attitude=attitude,jointAngles=joints,components=components,aux=aux)

def notification(name,m):
    body=bytes.fromhex(m['payloadHex']);flags=m['flags']
    if not integer(flags) or not 0<=flags<=255 or flags&0x87:return None
    if (m['commandSet'],m['commandId'])==(4,5) and name=='telemetry':
        try:return telemetry(body)
        except ValueError:return None
    if m['sender']!=4 or m['receiver']!=2 or m['commandSet']!=4:return None
    try:
        if name=='sensor' and m['commandId']==48:return sensor(body)
        if name=='program' and m['commandId'] in (56,100,107):return program(body,m['commandId'])
        if name=='abnormal' and m['commandId']==39:return abnormal(body)
        if name=='calibration' and m['commandId']==110:
            r=calibration(body);return r if r['rawState'] is not None else None
    except (ValueError,IndexError):pass
    return None

def perform(c):
    op=c['op'];k=c.get('args',{})
    if op=='frame':return frame(k['sequence'],k['commandSet'],k['commandId'],bytes.fromhex(k.get('payloadHex','')),k.get('flags',0),k.get('sender',2),k.get('receiver',4)).hex()
    if op=='parse':return parse(bytes.fromhex(k['hex']))
    if op=='payload':return payload(c['kind'],**k).hex()
    if op=='selection':return selection(**k)
    if op=='parameters':return parameters_reply(bytes.fromhex(k['hex']),k['parameters'])
    if op=='decode':
        b=bytes.fromhex(k['hex']);name=c['kind']
        if name=='telemetry':return telemetry(b)
        if name=='calibration':return calibration(b)
        if name=='sensor':return sensor(b)
        if name=='component':return component(b)
        if name=='program':return program(b,k['commandId'])
        if name=='abnormal':return abnormal(b)
        if name=='center':return center(b,k['sourceVersion'])
    if op=='notification':return notification(c['kind'],k)
    if op=='stream':
        decoder=Stream(k.get('limit',8192));messages=[]
        for chunk in k['chunks']:messages.extend(decoder.feed(bytes.fromhex(chunk)))
        return dict(messages=messages,invalidFrames=decoder.invalidFrames,discardedBytes=decoder.discardedBytes,bufferHex=decoder.buffer.hex())
    raise ValueError('unknown operation')

def clean(v):
    if isinstance(v,float) and not math.isfinite(v):return None
    if isinstance(v,float) and v==0:return 0
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
    if isinstance(v,list):return [clean(x) for x in v]
    return v

if __name__=='__main__':
    if '--self-test' in sys.argv:
        stop=frame(256,4,1,payload('velocity'))
        need(stop.hex()=='551604fc020400010004010004000400040000027705')
        d=Stream();r=[]
        for b in stop:r.extend(d.feed(bytes((b,))))
        need(len(r)==1 and r[0]['sequence']==256 and not d.invalidFrames)
        print('reference self-test passed')
    else:
        output=[]
        for case in json.load(sys.stdin):
            try:output.append(dict(ok=True,value=clean(perform(case))))
            except (ValueError,KeyError,TypeError,IndexError,OverflowError,struct.error):output.append(dict(ok=False))
        print(json.dumps(output,allow_nan=False,separators=(',',':')))
```
<!-- REFERENCE_PYTHON_END -->

将此代码块原样保存为`reference.py`，执行`python3 reference.py --self-test`做最小自检；不带参数时从stdin读取JSON测试用例数组，逐项输出`{ok,value}`或`{ok:false}`。字节在测试接口用hex字符串表示，实际GATT传输仍是原始bytes。

<!-- GOLDEN_VECTORS_BEGIN -->
### 16.1 完整合成帧向量

以下均为公开合成示例，序号固定256；`AI42`是虚构SN，非用户数据。字段为十进制JSON，frameHex/payloadHex为十六进制。flags未给时为0，sender/receiver未给时为2/4。每项是一条DUML帧，不包含第12节可能附加的先行/收尾中位帧，不是完整连接会话脚本。例程不要求逐条向真机发送，尤其维护和研究包只供离线核对。

```json
[
  {
    "name": "stop",
    "commandSet": 4,
    "commandId": 1,
    "flags": 0,
    "payloadHex": "000400040004000002",
    "sequence": 256,
    "frameHex": "551604fc020400010004010004000400040000027705"
  },
  {
    "name": "pan-positive-0.1",
    "commandSet": 4,
    "commandId": 1,
    "payloadHex": "000400044204000002",
    "sequence": 256,
    "frameHex": "551604fc02040001000401000400044204000002ddd2"
  },
  {
    "name": "recenter",
    "commandSet": 4,
    "commandId": 76,
    "flags": 64,
    "payloadHex": "fe01",
    "sequence": 256,
    "frameHex": "550f04a20204000140044cfe01bc6a"
  },
  {
    "name": "degree-info",
    "commandSet": 4,
    "commandId": 30,
    "flags": 64,
    "payloadHex": "",
    "sequence": 256,
    "frameHex": "550d04330204000140041ea767"
  },
  {
    "name": "sensitivity-read",
    "commandSet": 4,
    "commandId": 16,
    "flags": 64,
    "payloadHex": "96",
    "sequence": 256,
    "frameHex": "550e04660204000140041096212f"
  },
  {
    "name": "sensitivity-read-ACK-header9",
    "commandSet": 4,
    "commandId": 16,
    "flags": 128,
    "sender": 4,
    "receiver": 2,
    "payloadHex": "00960901",
    "sequence": 256,
    "frameHex": "5511049204020001800410009609014b12"
  },
  {
    "name": "sensitivity-write1",
    "commandSet": 4,
    "commandId": 15,
    "flags": 64,
    "payloadHex": "960101",
    "sequence": 256,
    "frameHex": "551004560204000140040f9601018e63"
  },
  {
    "name": "parameter-write-ACK",
    "commandSet": 4,
    "commandId": 15,
    "flags": 128,
    "sender": 4,
    "receiver": 2,
    "payloadHex": "00",
    "sequence": 256,
    "frameHex": "550e04660402000180040f0062b6"
  },
  {
    "name": "follow-pitch-acceleration1",
    "commandSet": 4,
    "commandId": 15,
    "flags": 64,
    "payloadHex": "0f020100",
    "sequence": 256,
    "frameHex": "551104920204000140040f0f020100e117"
  },
  {
    "name": "follow-speed-pitch-high-raw55",
    "commandSet": 4,
    "commandId": 15,
    "flags": 64,
    "payloadHex": "41015d",
    "sequence": 256,
    "frameHex": "551004560204000140040f41015d6df8"
  },
  {
    "name": "standalone-pitch-speed50",
    "commandSet": 4,
    "commandId": 15,
    "flags": 64,
    "payloadHex": "48010250023200",
    "sequence": 256,
    "frameHex": "5514046d0204000140040f480102500232008bc5"
  },
  {
    "name": "motor-pitch-stiffness-read",
    "commandSet": 4,
    "commandId": 50,
    "flags": 64,
    "payloadHex": "00",
    "sequence": 256,
    "frameHex": "550e046602040001400432001dce"
  },
  {
    "name": "motor-pitch-stiffness-read-ACK41",
    "commandSet": 4,
    "commandId": 50,
    "flags": 128,
    "sender": 4,
    "receiver": 2,
    "payloadHex": "00000129",
    "sequence": 256,
    "frameHex": "5511049204020001800432000001297858"
  },
  {
    "name": "motor-pitch-stiffness-write41",
    "commandSet": 4,
    "commandId": 49,
    "flags": 64,
    "payloadHex": "000129",
    "sequence": 256,
    "frameHex": "5510045602040001400431000129d473"
  },
  {
    "name": "smooth-yaw-true-roll-false",
    "commandSet": 4,
    "commandId": 15,
    "flags": 64,
    "payloadHex": "110101130100",
    "sequence": 256,
    "frameHex": "551304030204000140040f1101011301005abb"
  },
  {
    "name": "axis-mode-ThreeDRoll360",
    "commandSet": 4,
    "commandId": 15,
    "flags": 64,
    "payloadHex": "220118",
    "sequence": 256,
    "frameHex": "551004560204000140040f220118ed07"
  },
  {
    "name": "profile2",
    "commandSet": 4,
    "commandId": 15,
    "flags": 64,
    "payloadHex": "000102",
    "sequence": 256,
    "frameHex": "551004560204000140040f000102b50e"
  },
  {
    "name": "work-mode-Center",
    "commandSet": 4,
    "commandId": 15,
    "flags": 64,
    "payloadHex": "3e0103",
    "sequence": 256,
    "frameHex": "551004560204000140040f3e01038989"
  },
  {
    "name": "fine-pitch-minus2",
    "commandSet": 4,
    "commandId": 7,
    "flags": 64,
    "payloadHex": "ec02",
    "sequence": 256,
    "frameHex": "550f04a202040001400407ec02d6d1"
  },
  {
    "name": "autotune-start",
    "commandSet": 4,
    "commandId": 106,
    "flags": 0,
    "payloadHex": "000101",
    "sequence": 256,
    "frameHex": "551004560204000100046a0001014cc9"
  },
  {
    "name": "autotune-stop",
    "commandSet": 4,
    "commandId": 106,
    "flags": 0,
    "payloadHex": "000100",
    "sequence": 256,
    "frameHex": "551004560204000100046a000100c5d8"
  },
  {
    "name": "autotune-complete-push",
    "commandSet": 4,
    "commandId": 110,
    "flags": 0,
    "sender": 4,
    "receiver": 2,
    "payloadHex": "00020264",
    "sequence": 256,
    "frameHex": "551104920402000100046e0002026406da"
  },
  {
    "name": "horizontal-AUTO",
    "commandSet": 4,
    "commandId": 8,
    "flags": 64,
    "payloadHex": "00",
    "sequence": 256,
    "frameHex": "550e04660204000140040800cf85"
  },
  {
    "name": "horizontal-ACK",
    "commandSet": 4,
    "commandId": 8,
    "flags": 128,
    "sender": 4,
    "receiver": 2,
    "payloadHex": "000001aa",
    "sequence": 256,
    "frameHex": "5511049204020001800408000001aa9276"
  },
  {
    "name": "horizontal-complete-push",
    "commandSet": 4,
    "commandId": 48,
    "flags": 0,
    "sender": 4,
    "receiver": 2,
    "payloadHex": "6400aa",
    "sequence": 256,
    "frameHex": "55100456040200010004306400aa14e8"
  },
  {
    "name": "program-single-track",
    "commandSet": 4,
    "commandId": 107,
    "flags": 64,
    "payloadHex": "00020162",
    "sequence": 256,
    "frameHex": "551104920204000140046b00020162af69"
  },
  {
    "name": "program-single-timelapse",
    "commandSet": 4,
    "commandId": 107,
    "flags": 64,
    "payloadHex": "00020137",
    "sequence": 256,
    "frameHex": "551104920204000140046b00020137876c"
  },
  {
    "name": "program-single-panorama",
    "commandSet": 4,
    "commandId": 107,
    "flags": 64,
    "payloadHex": "00020163",
    "sequence": 256,
    "frameHex": "551104920204000140046b000201632678"
  },
  {
    "name": "track-status-record",
    "commandSet": 4,
    "commandId": 107,
    "flags": 0,
    "sender": 4,
    "receiver": 2,
    "payloadHex": "00620401020304",
    "sequence": 256,
    "frameHex": "5514046d0402000100046b00620401020304e1cb"
  },
  {
    "name": "standalone-timelapse-status",
    "commandSet": 4,
    "commandId": 56,
    "flags": 0,
    "sender": 4,
    "receiver": 2,
    "payloadHex": "ff020304",
    "sequence": 256,
    "frameHex": "5511049204020001000438ff020304f02b"
  },
  {
    "name": "standalone-panorama-status",
    "commandSet": 4,
    "commandId": 100,
    "flags": 0,
    "sender": 4,
    "receiver": 2,
    "payloadHex": "00ffff0080",
    "sequence": 256,
    "frameHex": "551204c70402000100046400ffff0080d6b7"
  },
  {
    "name": "abnormal-status",
    "commandSet": 4,
    "commandId": 39,
    "flags": 0,
    "sender": 4,
    "receiver": 2,
    "payloadHex": "04ff3e6701aabb",
    "sequence": 256,
    "frameHex": "5514046d0402000100042704ff3e6701aabb3118"
  },
  {
    "name": "CENTER-Ver1_1-read",
    "commandSet": 0,
    "commandId": 50,
    "flags": 64,
    "receiver": 229,
    "payloadHex": "11",
    "sequence": 256,
    "frameHex": "550e046602e50001400032113911"
  },
  {
    "name": "CENTER-synthetic-ACK-AI42",
    "commandSet": 0,
    "commandId": 50,
    "flags": 128,
    "sender": 229,
    "receiver": 2,
    "payloadHex": "0001ea070a150c22380441493432",
    "sequence": 256,
    "frameHex": "551b0475e50200018000320001ea070a150c22380441493432422a"
  },
  {
    "name": "synthetic-telemetry49",
    "commandSet": 4,
    "commandId": 5,
    "flags": 0,
    "sender": 4,
    "receiver": 2,
    "payloadHex": "85ff2d00070703fe7b00112200000000c8230000f8fffbff0000803f000000000000000000000000000000000000000000",
    "sequence": 256,
    "frameHex": "553e044b0402000100040585ff2d00070703fe7b00112200000000c8230000f8fffbff0000803f0000000000000000000000000000000000000000003445"
  },
  {
    "name": "research-query-version",
    "commandSet": 0,
    "commandId": 1,
    "flags": 64,
    "payloadHex": "",
    "sequence": 256,
    "frameHex": "550d043302040001400001b1e8"
  },
  {
    "name": "research-query-controlStatus",
    "commandSet": 4,
    "commandId": 11,
    "flags": 64,
    "payloadHex": "",
    "sequence": 256,
    "frameHex": "550d04330204000140040b8b20"
  },
  {
    "name": "research-query-type",
    "commandSet": 4,
    "commandId": 28,
    "flags": 64,
    "payloadHex": "",
    "sequence": 256,
    "frameHex": "550d04330204000140041cb544"
  },
  {
    "name": "research-absolute-pan1.25",
    "commandSet": 4,
    "commandId": 20,
    "flags": 64,
    "payloadHex": "0d00000000000d14",
    "sequence": 256,
    "frameHex": "551504a9020400014004140d00000000000d1419f2"
  },
  {
    "name": "research-rate-release",
    "commandSet": 4,
    "commandId": 12,
    "flags": 64,
    "payloadHex": "00000000000000",
    "sequence": 256,
    "frameHex": "5514046d0204000140040c00000000000000aea1"
  },
  {
    "name": "research-sleep-rs3",
    "commandSet": 4,
    "commandId": 15,
    "flags": 64,
    "payloadHex": "230101",
    "sequence": 256,
    "frameHex": "551004560204000140040f23010171d0"
  },
  {
    "name": "research-sleep-rs3mini",
    "commandSet": 4,
    "commandId": 15,
    "flags": 64,
    "payloadHex": "230111",
    "sequence": 256,
    "frameHex": "551004560204000140040f230111f0c0"
  }
]
```
<!-- GOLDEN_VECTORS_END -->

<!-- PUBLIC_API_BEGIN -->
### 16.2 当前公开原型成员清单

仅列公开方法和getter名，不包括构造器、下划线内部方法、实例回调字段或Python别名。继承成员由父层提供，不应建立重复连接。

```json
{
  "BleDevice": [
    "activeOperation",
    "close",
    "connect",
    "connected",
    "disableAutoReconnect",
    "disconnect",
    "enableAutoReconnect",
    "getAttitude",
    "getJointAngles",
    "latestTelemetry",
    "recenter",
    "reconnectState",
    "requestDegreeInfo",
    "setVelocity",
    "stop",
    "velocity"
  ],
  "AppCommands": [
    "abnormalStatus",
    "calibrationStatus",
    "getAxisMode",
    "getCenterActivationInfo",
    "getCustomFollowSettings",
    "getFollowSensitivity",
    "getFollowSettings",
    "getFollowTuning",
    "getMotorSettings",
    "getMotorTuning",
    "getRcSettings",
    "getRcTuning",
    "getSmoothTrackAxes",
    "getStandaloneTuning",
    "getUserProfile",
    "getWorkMode",
    "profile",
    "programStatus",
    "readParameters",
    "sendAutoTuneRequest",
    "sendAxisModeRequest",
    "sendComponentCalibrationRequest",
    "sendFineTuneRequest",
    "sendProgramStatusRequest",
    "sendSmoothTrackAxesRequest",
    "sendUserProfileRequest",
    "sendWorkModeRequest",
    "sensorCalibrationStatus",
    "setCustomFollowSettings",
    "setFollowSensitivity",
    "setFollowSettings",
    "setFollowTuning",
    "setMotorSettings",
    "setMotorTuning",
    "setRcSettings",
    "setRcTuning",
    "setStandaloneTuning",
    "useProfile"
  ],
  "RS4Mini": [
    "captureHome",
    "getOrientation",
    "home",
    "moveFor",
    "moveHome",
    "moveThrough",
    "moveTo",
    "moveToActive",
    "runTrajectory",
    "setVelocityDeg",
    "trajectoryProgress"
  ],
  "ExperimentalDevice": [
    "profile",
    "query",
    "setSleep",
    "status",
    "useProfile"
  ],
  "ExperimentalGimbal": [
    "absolute",
    "rateFor"
  ]
}
```
<!-- PUBLIC_API_END -->


### 16.3 只凭本文件运行全部完整帧向量

将本文保存为SDK_RECONSTRUCTION_SPEC.md，使用以下脚本提取并核对，不需要原项目或第三方依赖。完整帧向量表不是参考CLI的op用例数组，下面将其显式转换。

```python
from pathlib import Path
import re, json
text = Path('SDK_RECONSTRUCTION_SPEC.md').read_text(encoding='utf-8')
def block(begin, end, lang):
    part = text.split('<!-- ' + begin + ' -->', 1)[1].split('<!-- ' + end + ' -->', 1)[0]
    fence = '`' * 3
    return re.search(fence + lang + r'\n([\s\S]*?)' + fence, part).group(1)
ns = {'__name__': 'reference_codec'}
exec(compile(block('REFERENCE_PYTHON_BEGIN','REFERENCE_PYTHON_END','python'), 'embedded-reference', 'exec'), ns)
vectors = json.loads(block('GOLDEN_VECTORS_BEGIN','GOLDEN_VECTORS_END','json'))
for v in vectors:
    r = ns['perform']({'op':'frame','args':v})
    assert r == v['frameHex'], v['name']
    parsed = ns['parse'](bytes.fromhex(r))
    assert parsed['payloadHex'] == v['payloadHex']
print('All', len(vectors), 'complete-frame vectors passed; no Bluetooth used')
```

## 17. 复刻顺序与验收要求

1. 先运行本文件内参考代码，验证附录完整帧、CRC、端点、序号、flags、payload；再验证任意1字节分片、粘包、噪声、CRC坏帧和超长缓存重同步。
2. 实现请求上下文参数解析，测试headerByte不等于size、index150、截断、错序、尾部剩余；逐项电机读取，不返回部分成功。
3. 实现所有命名payload，逐组核对两套索引命名空间、未知raw保留、负微调float32截断、motor enabled反位、bitfield保留位。
4. 用合成通知验证四类状态、不剥推送首字节、3种程序布局及两种校准枚举；通知不能完成查询/定位，坏帧不更新半份缓存，回调异常不传播破坏内部状态。
5. 用假BLE实现连接各阶段超时、取消、迟到成功清理、整帧写不可交错、stop抢占、写失败断线、重连速度0、不重放设置和动作。禁止默认测试连接真机。
6. 单独实现主机组合层与GUI，验证不编码/写GATT，全部复用设备SDK连接与操作槽。参数无效时不能发送中位帧。
7. 只有用户在场且明确允许时才做真机：先只读，再同值写回/回读，最后用户指定的小幅速度/停止/回中；校准与较大动作另按用户授权执行。接收到ACK不等于观察到实际效果。

当前文档参考实现与Node进行7,573个独立编解码/边界用例比对，42条完整合成帧，5个Node类72个公开原型成员及两份原生公开头一致；Python3.8和3.12运行通过。所有验证均无蓝牙初始化。此数量对应本规范版本1，不是硬件功能数量。

本仓库已有验收规模可作参考而非硬凑数量：Node228、Python3.8/3.12各209、研究558、native1562+236+3+210；Node0.7.39基础24/24及三种原始查询批次5/5实机通过。先前119项设置/读取、9项小幅速度/重连、6项偏离后回中以及校准/微调记录在对应版本下成立。不要把本文件的离线向量当新固件实测。

若有原仓库，运行`node tools/verify-reconstruction.mjs`会取出本文件内参考代码/向量，与当前Node纯codec和API逐项离线比较；不读取原始硬件抓包、不初始化蓝牙。没有原仓库时，使用本文件内的向量和参考代码自身即可开始独立实现。

## 18. 实现核查路径（非独立复刻的必需输入）

| 规则 | 基线源码 |
|---|---|
| CRC/帧/速度/回中 | node/src/protocol.js |
| 重组/04:05 | node/src/telemetry.js |
| 连接/队列/操作/停止 | node/src/device.js、noble-adapter.js、async.js |
| App事务/业务ACK | node/src/app-commands.js、app-protocol.js |
| 参数/bitfield/索引 | app-settings.js、app-tuning.js、app-standalone.js、app-motor.js、app-axis-mode.js、app-smooth-track.js、app-profile-values.js |
| 维护与状态 | app-calibration.js、app-component-calibration.js、app-sensor-calibration.js、app-fine-tune.js、app-program-request.js、app-program-status.js、app-source-status.js |
| CENTER | app-center-info.js |
| 研究分支 | experimental-device.js、experimental-protocol.js、experimental.js |
| 主机组合 | controller.js、position-settings.js、trajectory.js、orientation.js |
| Python/原生 | python/rs4mini_sdk、macos/RSBleDevice.m、RSControlCore.m、RSGimbal.m、RSMotionCore.m |
| GUI | macos/RSSDKActions.m、RSSDKPanel.m、controller.m |

正文不放真实设备标识UUID/SN、真实用户抓包或第三方APK派生物。后续SDK变更时必须同步更新本规范、参考代码、向量和API覆盖检查，并明确新的基线版本；不能把历史研究项无说明地混回保留功能表。
