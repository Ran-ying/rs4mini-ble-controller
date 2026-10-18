# 01/07代码备份槽位审计：不重建名称或DEX

2026-10-19。固定Ronin2.2.2 APK，仅标准库读取文件。工具[ronin_code_slots.py](ronin_code_slots.py)，证据[ronin-code-slots-evidence.json](../../protocol/research/ronin-code-slots-evidence.json)。不执行APK/Java/JNI/UI，不导入SDK，不生成或运行可解析DEX。

## 比原有限制前进了什么

原[六段恢复](CODE_BANKS.md)依据字符串id的未损坏后缀恢复具名元数据，再严格匹配49,542条代码备份。01/07整张字符串id表位于观察到的前128KiB损坏区，不能用同一佐证方法。现在独立利用损坏区之外的method_ids、class_defs和class_data，完成另外3,137条备份到准确code_off ULEB槽位的匹配，且核对方法所属类型的**数值索引**；没有恢复其字符串、类型或原型身份。

| 段 | 完整method_ids | class_defs | class_data | 数值方法槽位 | 匹配备份 | 匹配code_item字节 |
|---|---:|---:|---:|---:|---:|---:|
| 01 | 15,871 | 2,297 | 2,268 | 12,143 | 2,623 | 310,959 |
| 07 | 5,224 | 641 | 621 | 3,240 | 514 | 57,395 |

备份数不等于方法总数，更不等于设备命令数。与现有六段恢复记录合计是52,679条已定位备份；这没有把可读具名DEX范围从六段提升为八段。

## 为什么不能只补字符串表

以区间相交计算各表落在前0x20000的字节/条目，不把部分条目算作完整有效：

| 段 | 除header/string_ids外相交部分 |
|---|---|
| 01 | type_ids前3,111条，共12,444字节；该表总3,482条 |
| 07 | 全1,343条type_ids、全1,589条proto_ids、field_ids前35,508字节（涉及4,439条，最后一条仅部分） |

这解释了为什么不能按物理字符串顺序填表后便宣称恢复成功。探索中合法描述符形状候选也不与type_count一一对应；本工具不使用这些猜测。恢复类型表和原型表仍需要独立身份佐证或明确的保护层格式证据。

## 审计不需要具名类型

1. 固定APK SHA256、8个隐藏map、准确分段和dgc2条目名，复用既有严格备份表校验，不跨段匹配。
2. method_ids/class_defs必须完整位于损坏区之后；class_data指针与完整变长记录必须落在其映射区，唯一且不重叠，数量与map一致。类定义保留源顺序，不额外假定按type_idx排序。
3. method_ids的owner/proto/name数值索引必须在声明计数内，按DEX方法id规则唯一有序；不把数值name_idx转换为未经佐证的文本。
4. 独立遍历类方法槽位，并与既有encoded_methods读取器核对槽位集合、方法索引唯一性及method_ids中的owner与class_defs的类型索引一致。只在内存临时计数/偏移shim中供读取器使用，不写DEX魔数、类型/原型表或校验头，不输出该临时对象。
5. 所有备份必须匹配唯一准确ULEB槽位；目标代码4字节对齐且位于code_item区。当前/备份完整长度、指令单元数、异常表边界和目标不重叠继续验证。
6. 输出仅摘要与数值槽位/指纹。每段slotRecordSha256为按slot排序、sort_keys和紧凑JSON编码的完整记录摘要；可选完整记录保存在忽略研究目录，不含完整厂商代码。

这不是通过猜方法名称或取消旧恢复校验绕过限制。namedMetadataRestored、typeIdentityRecovered、prototypeIdentityRecovered、stringOrderIndependentlyCorroborated、parseableDexProduced全部false。现有六段具名DEX及其固定哈希保持不变；**不得将01/07加入现有具名BANKS/caller扫描，直到另行取得身份与完整结构证据。**

## 复现

```sh
PYTHONPATH=tools/research work/python312/bin/python tools/research/ronin_code_slots.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --output work/research/reproduced-code-slots.json \
  --slots-dir work/research/unresolved-slot-records
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_code_slots.py -v
```

最终工具对真实固定输入独立运行两次摘要一致。12项测试覆盖可信区域、归属索引、名称/原型计数、精确/重复槽位、大小/指令单元数、重叠、半条目损坏、输入哈希与未验证门槛。

运行时仍0.7.32/原生0.3.32；没有新增SDK收发、命令映射或高级功能，没有扫描、连接、移动硬件或执行厂商代码。01/07具名元数据仍未恢复，现有六段调用扫描也未升级为全App覆盖。48项清单与全命令/高级门槛仍false。
