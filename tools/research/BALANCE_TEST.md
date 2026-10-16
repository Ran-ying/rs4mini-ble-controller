# 平衡测试调用链与同名参数冲突

2026-10-16，运行时保持 Node/Python/Web0.7.6、原生0.3.6。该阶段为只读静态研究，没有执行App或硬件操作。后续0.7.7已封装接口，当前SDK范围与限制见 [APP_BALANCE_TEST.md](../../docs/APP_BALANCE_TEST.md)，本工具本身不提供SDK或发送能力。

HG724→HG702→Ronin2继承链未覆盖 `startGimbalBalanceTest()`。Ronin2实现以BaseCommand.BALANCE_TEST取名字 `balance_test`，值64传给 `setRonin2CommonUserParam()`，经 `DataGimbalSetUserParams/04:0F`。对应getter是 `DataGimbalGetUserParams/04:10`。因此不能因 `DataGimbalBalanceAdjust/04:40` 的类名而用它替代该路径；其他型号或业务路径可能使用40，本研究不否定它们。

## 同名记录必须保留

固定APK的 `res/DB.json` 中有两条同名balance_test：

| 资源数组序号（从0开始） | index | typeID | size | min/max |
|---|---|---|---|---|
| 36 | 37 | 0 | 1 | 0..1 |
| 74 | 37 | 0 | 1 | 0..255 |

参数加载线程选择gimbal_param_infos；readToMemory取得List并顺序迭代，将成功转换的记录以name为键HashMap.put。后一次成功插入替换此前同名项。不能使用“名字唯一”查找器，也不能取第一条记录后将64误判为非法值。本批保留两条及其顺序；没有把此规则扩展成任意参数写入。

现有公共用户参数编解码结合该静态路径得到候选请求体 `25 01 40`，读取体 `25`。这些字节不是已发送抓包；后续SDK仅按固定启动值开放；实机兼容、动作完成和中止仍待验收。不会假设写零就是停止。

## 结果字段

Ronin2的普通用户参数事件处理器读取同一命名参数：

- bits6..7：BalanceTestStatus，0 DEFAULT、1 TESTING、2 FINISH、3 ERROR。
- bits4..5：Roll结果；bits2..3：Pitch结果；bits0..1：Yaw结果。
- 每个结果字段减1作为枚举数组下标；枚举顺序PASS、MARGINAL、FAIL、UNKNOWN。因此线上字段1/2/3分别对应前三者，**0不是PASS**，不能将它当有效数组下标，也不能造出默认通过。

SDK后续需保留raw值、明确零字段处理，不能把状态FINISH视作对某个本机请求的关联完成。本研究没有程序ID、物理停止或订阅条件的证据，也不把App继承当作HG724固件/UI启用证明。

## 可复现证据

`ronin_balance_trace.py` 校验固定APK及恢复DEX哈希，核对命名键、两条资源记录、继承链、启动常量、参数管理器、事件位提取及枚举，保存14个方法指纹。输出仅元数据与选定事实，不包含完整厂商方法或资源。

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_balance_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --dex work/research/code-final/business-05-code-restored.dex \
  --output work/research/reproduced-balance-evidence.json
```

证据：[ronin-balance-evidence.json](../../protocol/research/ronin-balance-evidence.json)。标准库测试拒绝缺失/布局冲突的记录、不支持的枚举控制流、未解析构造和非固定APK，验证同名记录不会静默去重。可读恢复视图只供离线分析，不运行或发布。
