# 保存命令六段静态引用扫描

2026-10-17，运行时Node/Python/Web0.7.16、macOS0.3.16不变。新增标准库入口ronin_save_trace.py，实际解析可选Androguard；不导入SDK/UI，不构造DUML或发送，不执行APK/JVM/JNI。证据protocol/research/ronin-save-callers-evidence.json。

工具先核对固定Ronin APK及六段派生DEX哈希，全部成功后才加载解析器。逐段遍历带code的方法和指令，记录匹配方法位置/指纹与分类，不将完整反汇编或派生二进制入Git。新增五项测试验证内部/外部调用边界、分配/class/枚举/字符串不能算直接调用，以及APK/银行哈希失败前不解析。

| bank | 方法数 | 带code的方法 | 指令数 | 保存引用方法数 |
|---|---:|---:|---:|---:|
| 00 | 53828 | 50517 | 682926 | 0 |
| 02 | 15931 | 15446 | 249001 | 0 |
| 03 | 38674 | 36349 | 559947 | 0 |
| 04 | 56720 | 53246 | 587995 | 0 |
| 05 | 55055 | 53173 | 677878 | 4 |
| 06 | 48024 | 45737 | 705675 | 0 |

计数为逐段遍历之和，未做跨段去重。六段的总数是268232方法、254468带code的方法、3463422条指令，不是恢复出的原始方法总数；既有精确备份恢复记录仍为49542条，未恢复/保护桩限制没有取消。

四个方法均bank05：CmdIdGimbal.CmdIdType的$values与静态构造器（枚举/名字字符串），DataGimbalSaveUserParams的getInstance/start（自身分配/内部调用/枚举）。没有外部直接调用、外部new-instance或class常量候选。bank05字符串表仅类descriptor、Java源文件名和SaveUserParams枚举名，其他五段无匹配。

此前两段扫描的结论现在扩展到六段“指令引用”范围，仍不是全App：1/7段未恢复、其余保护桩/无code方法、间接反射或动态路径以及固件内持久化逻辑都未排除。源start空请求体/ACK只证明类能构造请求；没有HG724业务调用链，故不增加saveSettings或持久化承诺。也不把现有0F/31写入或13恢复设置等同保存。

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_save_trace.py --apk work/research/dji-ronin-2.2.2.apk --bank-dir work/research/code-banks --output work/research/save-six-banks-reproduced.json
```

证据中wholeAppRecovered/allScannedBodiesRecovered/indirectReflectionResolved/targetModelCallPathEstablished/targetDeviceVerified均false。命令清单关联新证据并保留04:11缺口；后续继续其他调用链和协议，禁止将负面检索结果写成目标设备不支持。没有操作硬件或新增高级功能。
