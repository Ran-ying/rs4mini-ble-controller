# HG724支持键：声明谓词与动作注册边界

2026-10-18，固定Ronin APK/bank05恢复视图。223个GimbalKeys声明字段、12方法指纹及两条动作注解见
[证据](../../protocol/research/ronin-key-support-evidence.json)。只读静态提取与手写规则模型，未加载Java类或执行反射/厂商代码。
运行时/安装包仍0.7.21 / 原生0.3.21，无SDK发送或高级新增。

## 提取范围与计数

只统计GimbalKeys自身声明的public static String且带Key/ComplexKey注解的字段：197个Key、26个ComplexKey，共223。
读取编译期字符串常量和Key注解默认值；没有把字段名当作运行时键字符串，也没有执行Field.get(null)。
固定源Key的included/excluded默认都是空数组，type默认Object，types默认空数组；accessType没有默认值，必须来自条目。

向源KeyInfo规则传入HG724类，并用同一固定DEX的父类/接口图检查匹配：
200个声明字段满足支持谓词，其中193个条目选择唯一，7个保留多候选；另23个不满足该谓词。
这不是200条BLE命令，也不是200项已验收能力；23个谓词false也不证明固件不支持相应协议。
范围不包括父目录继承字段、全部命令枚举或完整运行时注册结果。

## 实际源规则

| 位置 | 源行为 |
|---|---|
| parseAllKey | Key与ComplexKey不能同时存在；同时存在返回null |
| included/excluded列表 | 经过parseAllClass展开IAbstractionGroup；空输入/空数组返回null |
| 无包含项的条目 | 写defaultKey；多个默认条目以最后一个为准 |
| 包含项classKeyMap | 同一个精确Class键首次写入保留，重复只记录日志 |
| 排除集合 | 合并所有精确Class；构造末尾移除classKeyMap中完全相同的键 |
| support(Class) | null为false；unsupport.contains精确命中时false；有default则true，否则检查包含类isAssignableFrom |
| getKey(Class) | 遍历HashMap中的包含类，返回首个可赋值匹配；没有则返回default |

排除父类不是自动排除全部子类；包含父类却可以匹配子类。不能把两种规则合成同一个继承判断。
parseAllClass的非组分支会返回原始数组，源码code-unit46+0b跳到51的return，不是52的null返回。
本批12种包含/排除类引用都有定义且均未命中IAbstractionGroup接口；工具遇到未解析类或组引用会拒绝继续，绝不newInstance。
因此“源库使用反射展开组”不等于“研究工具已执行该反射”。

getKey没有“最具体子类优先”排序。7个多匹配字段为：
PitchSmoothTrackAcceleration/Deadband/Enabled/Speed、YawSmoothTrackAcceleration/Deadband/Speed。
HG724同时继承Handheld与Ronin2，两条注解分别可匹配；示例PitchSmoothTrackSpeed的原始accessType候选为3和6。
工具保留全部候选，不预测Class对象HashMap的实际迭代顺序，也不把原始accessType当DUML编号。

## 已核对的声明例子

| 声明字段 / 字符串键 | 支持谓词 | 单字段候选accessType原值 |
|---|---|---|
| ROTATE / Rotate | true | 8 |
| RESET_GIMBAL / ResetGimbal | true | 8 |
| MOTOR_ENABLED / MotorEnabled | true | 6 |
| USER_PROFILE / UserProfile | true | 6 |
| GIMBAL_WORK_MODE / GimbalWorkMode | true | 6 |
| FOLLOW_MODE_SENSITIVITY / FollowModeSensitivity | true | 6 |

HG724父类链还存在基础DJIGimbalAbstraction的@Action("Rotate")与@Action("ResetGimbal")，方法指纹已记录。
这补充了先前仅凭继承定位方法体的证据，仍不能跳过型号初始化、实际调用、协议路由和设备验收。

源initializeComponentCharacteristics调用addCharacteristics(GimbalKeys.class,getClass())；后者先support再getKey。
getKeyInfoMap实际使用getFields（含继承public字段），按字段String常量建立Map；
createMethodMap还遍历getMethods和父类方法，Getter/Setter/Action按源顺序分类并Map.put。
本批只记录这些框架方法，不执行反射、不完整模拟方法覆盖/调用或所有字段顺序。
继承目录字段、字面量键冲突、HG724初始化覆盖路径、方法Map顺序与虚方法调用仍需继续审计。
不能据一个动作注解就新增发送接口或宣称该动作可实际控制本机。

缓存键访问策略和原生DUML是不同层。一个原始accessType或缓存键支持不能替代参数索引/请求体/ACK证据，
也不能否定已有底层按上下文读取参数的协议实现；本批不改变任何SDK允许列表或参数发送行为。

## 复现

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_key_support.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --sdk work/research/code-banks/business-05-code-restored.dex \
  --output work/research/ronin-key-support-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_key_support.py -v
```

输入哈希先验证，后加载可选解析器。模型只复现已人工核对的KeyInfo包含/排除/默认规则，
不执行厂商指令、Android缓存、Java构造器或网络/蓝牙操作，不输出厂商反汇编。
未恢复代码、动态ClassLoader和固件差异仍是边界；全部命令完整性和高级新增门槛保持false。
