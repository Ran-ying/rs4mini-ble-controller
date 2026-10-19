# COMMON00:32激活状态与版本化报文源审计

2026-10-19，运行时保持0.7.32/原生0.3.32。新增八段具名视图的审计，固定56方法指纹。工具[ronin_activation_trace.py](ronin_activation_trace.py)，证据[ronin-activation-evidence.json](../../protocol/research/ronin-activation-evidence.json)。只读解析，不导入SDK、构造DUML帧、查询或激活设备，不执行App/UI/JNI。

## 命令与入口的已知部分

DataGimbalActiveStatus继承DataAbstractGetPushActiveStatus。其start指定APP→GIMBAL、REQUEST、ACK.YES、业务Encrypt.NO及COMMON/ActiveStatus，不是04命令集。

COMMON的源wire值为0；ActiveStatus构造为`[ActiveStatus,20,50,0,1,null]`，20是ordinal，50是命令号0x32。Class参数是**显式null**，不能把它变成DataGimbalActiveStatus推送绑定或自动通知解析规则。命令集中COMMON的DJICmdSetBase对象引用仍标为未解析，不伪造实例；这里只核对构造中的数值命令集，不声称恢复整个COMMON枚举或工厂。

新增bank01的ActiveDeviceController.activeGimbal(String)取GimbalActiveStatus，设置TYPE.SET、active=true、SN、年月日时分秒，然后调用start。ActiveWebController同时持有该状态类、OkHttpClient和缓存SN监听。这不证明所有步骤走网络，也不证明可脱离网络/服务校验直接写设备。HG724入口、实际BLE路由、绑定/持久化与最终加密条件尚未确定。

## 初始版本不是会话版本

GimbalActiveStatus单例首次创建时设置Ver1_1。但DataCommonActiveGetVer.setRecData还有版本更新路径：读取业务首字节→版本find→按DeviceType分支更新对应设备的激活单例。因此不能只读构造默认就固定使用新版。

版本查询源doPack为一字节`00`，同样使用COMMON/ActiveStatus；设备类型由调用方设置。源start含1000ms超时和repeatTimes2，SDK没有复制它的重试策略。后续[接收审计](ACTIVATION_RECEIVE.md)已核对基础COMMON表ACK返回码剥离，实际扩展/会话仍未验证；线上单个00在此条件下只有返回码，不能自动当版本0或完整成功业务体。

| 源版本名 | 源value | TYPE.value(version)分支 |
|---|---:|---|
| Ver1_0 | 0 | data |
| Ver1_1 | 1 | 非零data1，否则data |
| Ver1_3 | 3 | 非零data1，否则data |
| Ver13 | 51 | data；不是Ver1_3的别名 |
| OTHER | 100 | data；不是已支持目标版本 |

TYPE的源data/data1分别为GetVer0/0、GET1/17、SET2/18、PUSH3/19、FAIL4/20、GetStatus5/49、SetUerData6/51、SetWebData6/55、OTHER100/0。保留源拼写Uer；不能把这些业务值当独立DUML命令号。通用doPack已读GET/SET/FAIL分支，其他枚举及V13/V14专用推送处理不能仅凭值表视作已封装。

## SET布局与SN长度

这是离线源码布局，不是目标设备安全范围。工具仅计算布局元数据，不生成激活写入帧。

- 源SET头有类型、activeStatus及年/月/日/时/分/秒；实际时间来源/时区及业务校验未完成。
- Ver1_0分配19字节，SN从偏移9复制最多10字节，没有单独SN长度字节，未覆盖区保持零。
- 其他源版本分配`原SN字节数+10`，偏移9写`min(字节数,16)`，从偏移10复制最多16字节。SN超过16时，分配长度仍依原始字节数，末尾保留额外零字节；不能擅自规范成固定26字节或按字符数代替字节数。
- 字符编码、所有版本的业务用途、SN有效性与固件接受没有因此完成验收。布局助手必须显式传版本名及字节长度，不从默认状态猜测。

## 读取业务字段与包层边界

源getActiveStatus取业务偏移0的一字节bit0；getYear取业务偏移1的两字节。旧版SN在8起取10字节，带BATTERY receiver上下文的分支会用Invert变体，不能移植到GIMBAL；其他版本在8读长度，9起读SN，源长度>16回退空字符串。不能把空字符串、短包补零或单例旧缓存当作有效设备读数。

这些是业务方法偏移，不是已经确认的BLE payload偏移；ACK/推送/版本查询和V13/V14结构没有统一为一个运行时解码器。源getTime包含日期格式化，不据此保证本机时间/时区语义。

## 显式null解析的范围

旧constructor_records不支持把引用参数的literal0区分为null，仍保持原样。新解析器按构造参数类型区分：I/Z零是数值零，Class的已知零才是null；未知寄存器、字段读取或调用结果绝不自动变null。允许的其他不透明对象引用必须显式标记unresolvedReferenceType，并保存未解析参数位置。

本次只选择ActiveStatus和COMMON；COMMON构造前缀与之后的缓存循环分开，不能称完整COMMON枚举解析。分支、未知primitive/Class、错误类型、接收者、参数数量和重复标签仍拒绝，数组写入不会悄悄把未知值恢复成字面量。

八段限定扫描找到7个涉及GimbalActiveStatus或activeGimbal的直接调用方法、2个版本setter调用方法；这不排除反射、继承调用、native、别的注册路径或类库未被HG724启用。

## 复现

```sh
PYTHONPATH=work/research/analysis-libs:tools/research work/python312/bin/python tools/research/ronin_activation_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/prefix-restored-final-b \
  --output work/research/reproduced-activation.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_activation_trace.py -v
```

最终工具对真实固定输入独立提取两次，56方法证据一致。16项测试覆盖null/未知、限定作用域、寄存器覆盖、版本、SN长度/零尾部、八段哈希与未验证标志。完整厂商方法体不入库。

00:32作为源候选单列后清单为49个命令或缺口条目，不是49项设备能力或SDK接口。request/response封装仍unknown、无implementation。没有SDK收发、激活、相机/视觉或高级功能新增，没有扫描、连接、移动硬件/实时UI/厂商执行；inventoryComplete和advancedDevelopment.allowed仍false。

后续39方法接收审计见[ACTIVATION_RECEIVE.md](ACTIVATION_RECEIVE.md)：补基础表包层、条件反射名、源缓存赋值顺序及八段版本查询调用扫描；本页56方法的原证据保持历史范围，不改写为实机证据。

后续[GET/旧推送/V13/V14格式审计](ACTIVATION_FORMATS.md)固定34方法，保留SN转换及长度语义并隔离源自动回复；仍不是HG724协议或激活流程完成证明。
