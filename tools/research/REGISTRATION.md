# HG724初始化与两个动作的声明分派

2026-10-18，固定APK/bank05，19方法指纹。工具`ronin_registration_trace.py`只读DEX元数据与指令，
沿用[支持键审计](KEY_SUPPORT.md)的输入哈希和KeyInfo模型，不执行Java反射、初始化、厂商代码或BLE。
证据见[ronin-registration-evidence.json](../../protocol/research/ronin-registration-evidence.json)。
运行时/安装包仍0.7.21 / 原生0.3.21，没有新增SDK发送或高级功能。

## 目录继承补全

GimbalKeys父目录DJISDKCacheKeys有三个带Key注解的public static String：Connection、FirmwareVersion、SerialNumber。
NONE也是public static String但无相关注解，不进入此注解目录；TAG为private。加上此前223声明字段，共226个注解字段。
三个继承项都满足HG724源支持谓词；226项编译期字符串键无重复。无重复仅针对这些目录字段，
不能据此推断全部Getter/Setter/Action方法键也无冲突，更不是226条DUML命令。

## 源初始化声明链

HG724.init调用HG702.init；HG702无同签名声明，类链中最近声明为Ronin2.init。
之后依次向RoninBase、Handheld（同签名实际最近声明为Gimbal）、HW基类初始化。
HW.init调用initializeAllCharacteristics，再初始化子组件及createMethodMap。
initializeAllCharacteristics先initializeCommonCharacteristics（新建空Map），再虚调用initializeComponentCharacteristics。

HG724类链中最近的component声明是RoninBase；其super链依次Handheld、X3、Aircraft（实际声明Gimbal）。
前三个component实现均直接super后返回，Gimbal使用GimbalKeys.class和this.getClass()调用addCharacteristics。
因此静态声明链补齐了“仅看到基础方法体”的缺口；没有证明App本次确实创建HG724实例、所用index、
完整无异常运行初始化或动态缓存内容。init还包含监听/事件/能力初始化等副作用，本工具没有执行或全面模拟它们。

## Rotate与ResetGimbal

在完整HG724父类声明链中，这两个Action注解都定义于DJIGimbalAbstraction，方法为public，
精确名称+描述符的最近声明也都仍是该基础类，没有对应子类覆盖声明。这里只覆盖两个动作，
没有声称全部注解、接口分派或运行时方法注册均已完成。

createMethodMap先加入this.getClass().getMethods()，再加入各父类getMethods()，按Getter→Setter→Action分类并Map.put。
反射数组顺序未确定；源addActionMethod还允许后续替换动作Map，不能把本次元数据清单当成最终运行时Map。

performAction在非子组件路径核对非空参数键、characteristicsMap、actionMethodMap及isParamTypeCorrect，
再创建DefaultActionInnerCallback，prepend到参数数组，Method.invoke(this,args)。
工具只记录这些源方法指纹和调用标记；没有执行invoke，也未完整审计参数校验、回调缓存/超时和后续动态Map修改。
源文件中出现反射API是审计对象，不是研究工具的执行机制。

已有角度/回中请求路由、EYE依赖、型号地址和物理完成等边界仍按
[ANGLES.md](ANGLES.md)、[ANGLE_CONTEXT.md](ANGLE_CONTEXT.md)、[RESET_ROUTES.md](RESET_ROUTES.md)分别验收。
这批证据不自动把原生角度升级为本机支持，不开放单轴回中，不把动作回调当到位。

## 复现

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_registration_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --sdk work/research/code-banks/business-05-code-restored.dex \
  --output work/research/ronin-registration-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_registration_trace.py -v
```

所有提取均在固定哈希验证后进行，不输出厂商完整反汇编。nearest_declaration只查精确类链声明，
不模拟Java getMethods顺序/访问控制/接口方法或运行时反射；有接口时工具拒绝继续本范围的目标链审计。
未恢复银行、动态装载、其他动作/设置、固件差异和实机验收仍未完成，完整命令与高级新增门槛保持false。
