# 八段具名DEX恢复：保护库静态线索与独立SM4实现

2026-10-19。此批突破01/07具名元数据缺口：固定APK的**8段现在均产生可解析的具名离线视图**，共匹配52,679条代码备份。不代表全部App/native/VM恢复或全部BLE协议完成。没有执行APK、Java、JNI、原生库、UI或硬件。

工具[ronin_prefix_restore.py](ronin_prefix_restore.py)，[恢复证据](../../protocol/research/ronin-prefix-restoration-evidence.json)、[独立交叉核对](../../protocol/research/ronin-prefix-independent-validation.json)、[新增调用者](../../protocol/research/ronin-prefix-new-callers.json)。运行时仍0.7.32/原生0.3.32。

## 恢复依据

外层BDOVL常量与load方法选择AppGuard库，XGYKK.attachBaseContext调用该加载路径。固定arm64库为lib/arm64-v8a/libAppGuard.so，SHA256 fe1b0224cb5011efef6c8f4331bd0f3e13f49a38629f9ad48ae075bf60840ecb；不是仅凭名字猜选的libappsec.so。

保护库外包装在文件0xc010有固定标记，0xc020给出嵌入数据偏移0x18000。对嵌入数据作XOR0xba后，程序头、动态表及JNI_OnLoad/BDOVL/XGYKK等字符串形成一致结构。首64字节仍有其他保护，本工具不恢复或输出可加载原生库，也不把静态数据视图当已恢复可执行库。

嵌入数据的源前缀分发在0x213fc一带取min(size,0x20000)，逐16字节处理；0x26bbc的FK/CK/S盒与轮转、0x26d08起的反向轮密钥路径支持SM4解密。工具从固定数据取表和种子，结合源包名com.dji.ronin派生16字节键；只发布变换、常量/区域指纹和键摘要，不运行厂商指令或通用模拟器。实现为自写标准库SM4-ECB，无SDK引用。

## 不能只验证DEX魔数

每段完成以下检查才保存视图：

1. 固定APK/保护库哈希、准确8个map和分段dgc2名称；完整前128KiB按SM4解码。
2. 原头magic039、header_size112、endian、文件声明长度、map指针和六组id表计数/偏移与独立map一致。data_size+data_off对应备份前originalSize，文件声明长度还包含保护容器尾部，二者不能混用。
3. **解码后的完整保护容器Adler32与源头值一致，8段全部通过。** 源头SHA1与保护容器不匹配，记录为false，不替厂商重新解释或抹掉该事实。
4. 复用严格备份匹配：准确code_off ULEB槽位、当前/备份完整代码长度及指令单元数、异常表和目标不重叠。
5. 六个旧视图先验证原固定SHA256，再比较[112,originalSize)的完整元数据/代码字节，全部一致。旧文件不改写。
6. 恢复视图重新生成自身SHA1/Adler32；这是派生文件完整性，不证明与原始未保护DEX逐字节相同。新视图另有固定SHA256。
7. 真实输入独立复现两次结果一致；OpenSSL SM4-ECB与自写解码器对八段完整前缀共1,048,576字节逐字节匹配。另有标准SM4已知向量和轮密钥测试。

因此，不能宣称“源原始SHA1已验证”或“完整未保护App已恢复”；可以确认当前具名元数据与所选代码备份已形成可重复、独立核对的八段视图。

| 段 | class_defs | 备份code_item |
|---|---:|---:|
| 00 | 7,119 | 16,898 |
| 01 | 2,297 | 2,623 |
| 02 | 2,110 | 2,689 |
| 03 | 6,683 | 6,542 |
| 04 | 6,696 | 1,786 |
| 05 | 8,571 | 19,436 |
| 06 | 7,647 | 2,191 |
| 07 | 641 | 514 |

## 新增01/07的源引用补充

独立Androguard解析新增两段所有声明方法/原型及含代码方法的指令：01为12,143个声明方法、11,452个含代码方法；07为3,240/2,977。限定稳定器类/抽象/命令枚举的直接invoke扫描在01找到19方法、60处调用，07为0。以实际invoke目标分类，不把参数/返回类型提及当作直接调用。

新增引用包括ActiveDeviceController/ActiveWebController的激活状态类、通用FPV摇杆/创建控件，以及焦点组件。**这是类库源引用，不是HG724业务入口或BLE支持证明。** 相机/焦点名字只作为静态覆盖记录保留，没有新增相机接口、激活写入或其他SDK发送；需要逐项区分网络、BLE、型号和实际调用链。

旧六段审计、BANKS和证据保持历史复现范围；它们的“01/07未恢复”是当时状态。**当前新研究优先使用PREFIX_BANKS及business-XX-prefix-code-restored.dex**；不要将新旧两种文件哈希/头部长度混用。旧调用者结论也不能仅改文字便算八段重审完成，新补充只覆盖本页明确的直接引用模式。

## 复现

默认核心只依赖标准库；可选调用者解析使用已有独立Androguard环境：

```sh
PYTHONPATH=tools/research work/python312/bin/python tools/research/ronin_prefix_restore.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --baseline-dir work/research/code-banks \
  --output work/research/prefix-restored
PYTHONPATH=work/research/analysis-libs:tools/research work/python312/bin/python tools/research/ronin_prefix_restore.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --baseline-dir work/research/code-banks \
  --output work/research/prefix-restored-inspected --inspect-new-banks
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_prefix_restore.py -v
```

DEX、原生库、分析节区视图、反汇编和密钥候选均留在忽略work目录，不安装、加载、运行或入Git。仓库只保存自写恢复工具、元数据/指纹和证据摘要。

16项新测试覆盖SM4已知向量/多块/输入域、轮密钥、源Adler与SHA1区别、头/表/边界校验、固定哈希预检查和补充调用者范围。全部命令与高级开发门槛仍false；下一步优先审计新增激活/通用控制引用及重新扩大必要的命令调用扫描，仍需本机固件验证。
