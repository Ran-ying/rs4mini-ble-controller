# MSDK 4.18 候选协议：只读提取与离线核对

> 历史阶段说明：后续已发现当前 APK 的代码备份并恢复关键方法，参见 [CODE_RESTORATION.md](CODE_RESTORATION.md)。下文保留当时的元数据/旧 SDK 视图边界。

2026-10-16。SDK 运行时仍为 0.7.2；本轮只增加研究工具，没有新蓝牙发送接口或高级功能。

## 来源与可信边界

[DJI 官方仓库](https://github.com/dji-sdk/Mobile-SDK-Android/blob/master/README.md) 列出的 Maven 坐标为
`com.dji:dji-sdk-provided:4.18`。下载 [provided JAR](https://repo.maven.apache.org/maven2/com/dji/dji-sdk-provided/4.18/dji-sdk-provided-4.18.jar)，
SHA256 `f253d8ef033423132d35c28d5c0da0aade2e660d18f1994c56dec630e3f48f20`，
Maven SHA1 `907999976ba655d462c7bd6c6c7f784006ced5d9` 与下载内容一致。
该 SDK 面向其支持的 DJI 产品，不能推定支持 RS 4 Mini。

它是 compile-only 提供包。多数目标方法以提前返回开始，后面仍保留可结构化读取的字节码尾部；
工具保留返回前缀和所有指令偏移，不删除返回指令，不将不可达代码变成可执行程序。
这些尾部只作为静态候选逻辑，不能声称已恢复当前 Ronin App 的保护方法。
另检查了同版本运行时 AAR 的嵌入 JAR，没有发现这些同名 Gimbal 类；没有据此取得运行时交叉证据。

`protocol/research/msdk-4.18-evidence.json`（从仓库根目录读取）保存材料、类和方法指纹及人工核对的候选事实。
原始 JAR/AAR、完整反汇编和输出的完整指令清单仅在忽略目录，不随源码分发。

## 已得到的候选结构

### 04:4C 回中/模式

`DataGimbalNewResetAndSetMode.doPack()` 的不可达尾部创建两个字节：
第 0 字节为 `MODE.value()`，第 1 字节在 center 枚举不是 INVALID 时写入对应值，否则保持零。
`MODE` 候选枚举：YawNoFollow=0、FPV=1、YawFollow=2、OTHER=254。
center 枚举：YAW_CENTER=1、PITCH_YAW_CENTER=3、PITCH_CENTER=4、
PITCH_UP_OR_DOWN_WITH_YAW_CENTER=11、PITCH_UP_OR_DOWN=12、INVALID=255。
INVALID 是软件哨兵，不能把 255 当作该方法会发送的第 1 字节。

**这些名称不能直接变成本机模式或按轴 API。** 本机历史中 `FE01` 是三轴回中，
而旧枚举把 1 命名为 YAW_CENTER，已出现语义差异。当前 Ronin 2.2.2 同名类的可读构造函数与
`setReset(boolean)` 使用布尔字段，旧 MSDK 则用 ReturnCenterCmd 枚举，不能当成同一实现。
没有发送 `FE04` 或任何新的模式/轴候选。

### 04:32 Ronin 参数读取

`DataGimbalRoninGetUserParams` 的 `start()` 尾部引用旧名称 RobinGetParams，枚举常量为 0x32。
请求尾部按名字从外部参数表取得 index，每项写入一个字节。响应业务解码尾部按请求顺序
检查 index，跳过两个字节，再依赖外部 `ParamInfo.size/type` 读取值；不证明第二字节可独立作为宽度。
因此不能把它直接当成自描述 TLV，也不能只靠线上 index 推断名称和数值类型。

接收包类 `dji.midware.data.packages.P3.gfd` 的尾部先读取 response 位，再按命令元数据决定
是否将绝对帧偏移 11 的字节作为返回码，并从偏移 12 而非 11 开始复制业务数据。
`DataBase.setRecData()` 只保存传入的业务数组。**业务方法 offset 0 不等于原始 BLE payload offset 0。**
当前工具只接受调用方已明确分离返回码的业务体，不猜返回码存在性或成功语义。

### 04:35/36 手柄参数

旧 `SetHandleParams.doPack()` 尾部构造 8 字节；`GetHandleParams` 的业务读取偏移相互对应。
前五项依次为双通道、Tilt 方向、Pan 方向、profile、pitchFree 的原始字节。
不推断开关有效值、方向枚举或 PF/PTF/FPV 对应关系。后 3 字节涉及其他选项，离线工具保留为原始十六进制；
不引入相机功能，不开放写入，不声明这些字段适用于 RS 4 Mini。

## 复现

无需 Java、Android、Androguard、SDK Key 或蓝牙。仅使用 Python 标准库；输入先核对完整 SHA256，
不匹配时不会建立输出目录。下载与解析不执行厂商代码。

```sh
mkdir -p work/research
curl -fL 'https://repo.maven.apache.org/maven2/com/dji/dji-sdk-provided/4.18/dji-sdk-provided-4.18.jar' -o work/research/dji-sdk-provided-4.18.jar
python3 tools/research/msdk_static.py --jar work/research/dji-sdk-provided-4.18.jar --output work/research/msdk-static
python3 -m unittest discover -s tools/research -v
```

研究查看器不是通用 JVM 验证器：只支持已检查的 Java 8 classfile 格式；仅按 ASCII 解释协议标识，
其他常量转义保存；不调用字符串解密函数。枚举只识别相邻常量、构造和静态字段赋值的窄模式，
遇到分支拒绝猜测。指令解析检查截断、switch/wide 长度和跳转边界。
格式依据：[JVM classfile](https://docs.oracle.com/javase/specs/jvms/se8/html/jvms-4.html)、
[JVM 指令](https://docs.oracle.com/javase/specs/jvms/se8/html/jvms-6.html)。

## 离线候选载荷工具

`msdk_payloads.py` 不构造 DUML 帧，没有传输、设备或 SDK 导入，也不被 SDK/UI 引用。
只用于对照明确来源的样本；输出是候选字节，不能据此直接发送设备。

- `reset_mode_payload(mode, center_command)`：显式原始枚举值，INVALID/None 保持第二字节为零；没有 pan/tilt/roll 便捷 API。
- `ronin_parameter_request(indexes)`：保留调用方提供的原始索引顺序和重复项；不映射参数名。
- `ronin_parameter_body(body, requested)`：要求外部提供每个 index/size 上下文；保留被跳过的头字节，值保持 hex，拒绝截断、错序和多余字节。
- `handle_parameter_body(body)`：严格 8 字节业务体，前五项保留原始数值，尾部不解释。

工具的严格核对不是原 SDK 静默跳过、部分写入状态的等价复刻；不能以通过合成向量作为设备兼容证据。
下一步需要当前型号的有效业务实现、返回码规则、参数表选择路径或受控实机样本。完整命令门槛保持未通过。
