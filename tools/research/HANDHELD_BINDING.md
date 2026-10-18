# HG724手柄工厂与04:58 Setter绑定

2026-10-19，接续[手柄状态与通用发送类](HANDHELD_STICK.md)。固定APK和已恢复bank05，19方法指纹以及类、字段、方法注解元数据。仅静态读取，不执行APK、反射、类初始化、厂商方法或硬件。

## 先由工厂确认型号分支

DJISDKCacheHWAbstractionLayer.addHandheldControllerAbstraction读取PlatformType，经synthetic switch映射后选择手柄类。HG724映射值25，在当前packed-switch中跳到offset48，选择MobileHandheldControllerAbstraction。25是编译器switch值，不是PlatformType ordinal、型号线上字段或接收地址。

| 明确的来源平台条件 | 工厂选择 |
|---|---|
| HG724 | MobileHandheldControllerAbstraction |
| OSMO | HandheldControllerAbstraction |
| Ronin2 | 当前分支直接return，不新注册手柄类 |
| 未匹配分支 | 当前工厂不新注册，不能据此断言固件不支持 |

工厂传给addAbstraction的1是普通循环数量；该分支从index0构造，不得将这个1拿去改成BLE receiverId。反射构造、map已有值、异常及实际平台缓存仍会影响运行；本批只证明明确HG724源条件下的选择，未证明现场注册成功。

平台事件触发updateHandheldController，先移除旧HandheldController再调用工厂。所选Mobile类继承HandheldControllerAbstraction→HandheldControllerBaseAbstraction→通用HW抽象；Base初始化HandheldControllerKeys，并传运行时getClass作为抽象类型。

## 通过实际注解解释方法

HandheldControllerKeys的STICK_GIMBAL_CONTROL_ENABLED字面值为StickGimbalControlEnabled，Key注解accessType=6、includedAbstractions包含Mobile类、types数组为Boolean。保留types而不擅自改写成type；既有KeyInfo源谓词在该Mobile类型下得到单一、可注册的声明候选，不代表反射执行、实际调用或固件支持。

方法源码名虽为setIsInternalAndExternalMicroPhonesEnabled，其实际Setter注解却是`StickGimbalControlEnabled`。方法本身调用DataGimbalSetHandheldStickControlEnabled.setHandheldStickControlEnabled(bool)再start(callback)。因此不能按方法名创建麦克风控制接口，也不需要继续把它当作完全未绑定的通用类。

原来的只读审计已确认04:58的一字节00/01与请求ACK。本批补齐条件HG724工厂→手柄键支持→Setter注解→命令类调用的静态链；没有把它提升为本机发送成功、开关含义/持久化或04:57状态关联证明。

## 复现与下一步

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_handheld_binding.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --sdk work/research/code-banks/business-05-code-restored.dex \
  --output work/research/ronin-handheld-binding.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_handheld_binding.py -v
```

[证据JSON](../../protocol/research/ronin-handheld-binding-evidence.json)保存固定哈希、方法指纹、平台case/目标偏移、原始Key与Setter注解、继承和条件选择。寄存器解析只支持静态初始化所需的有限声明；遇分支/未知生产者即拒绝或丢弃旧值，不解释Java、反射或线程调度。

下一步可设计显式App来源的手柄控制开关候选请求，使用bool00/01、严格关联ACK、独占主机事务和取消无重放；不能自动订阅57、按ACK写回其状态、接管摇杆或推断相机/麦克风功能。实际设备开关效果、命令后运动行为及持久化仍待验收。

本批不新增SDK发送，运行时保持0.7.30/原生0.3.30；完整命令和高级开发门槛false。此前HANDHELD_STICK.md及旧证据中的“尚无HG724调用路径”记录为历史状态，由本次条件源链补充；实机支持仍未证明。


后续0.7.31已接入[手柄开关候选SDK](../../docs/APP_HANDHELD_STICK_CONTROL.md)。本研究检查点“未新增发送”保留为历史状态；只读工具仍不发送，真实设备效果仍未验收。
