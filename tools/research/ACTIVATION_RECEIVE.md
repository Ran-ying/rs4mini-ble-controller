# COMMON00:32版本响应与混合接收边界

2026-10-19；运行时保持0.7.32/原生0.3.32。工具[ronin_activation_receive.py](ronin_activation_receive.py)仅读取固定APK及八段具名分析视图；证据[ronin-activation-receive-evidence.json](../../protocol/research/ronin-activation-receive-evidence.json)固定39方法。没有执行App、Java反射、JNI、实时UI或操作硬件，没有SDK收发新增。

## 基础表的包层结论

ActiveStatus构造参数为`[ActiveStatus,20,50,0,1,null]`：isBlock=false、isMix=true、Class显式null。isNeedCcode不是其中的布尔参数，而是构造函数另行赋true。COMMON表继承DJICmdSetBase，RecvPack按命令表取isNeedCcode；未加密ACK的原始payload首字节为返回码，业务体从+1起，非ACK从+0起。

这只建立基础COMMON表的条件映射。CmdSet构造可以通过反射选择Extra扩展；实际会话选择、加密策略、HG724设备报文均未确认，不把业务Encrypt.NO当作最终明文保证。

COMMON回调成功码为0。另一个成功码1限定CAMERA，不适用于COMMON；源失败回调也可能存业务体，SDK不能据此把失败包更新为有效版本或激活状态。返回码0本身也不证明业务完整。

## 显式null不等于没有推送候选

null Class使DataUtil.getDataBaseInstRefl立即返回null；但管理器对非阻塞/混合命令还有模型名回退。COMMON普通规则以设备名称和ActiveStatus生成模型名；GIMBAL枚举使用普通构造、name=null，取Enum名称，经英文大小写规则生成`dji.midware.data.model.P3.DataGimbalActiveStatus`。该类在固定视图中存在并继承通用激活状态类。

所以基础表下processor及push两条路径均有资格，不能从显式null推断该命令没有推送路径。反射加载、取单例、服务状态及后续分发仍可能失败，不能声称每个ACK都会进入这个模型；本工具只静态检查源码，不调用Class.forName。

## 查询响应不能混成激活状态

通用激活模型setPushRecData先调用setRecData保存原始业务字节，之后才判断null、长度至少11、是否ACK。若短版本ACK确实经混合路径交付给该模型，则会先覆盖源状态缓存、再退出状态解析。这是源代码路径的可能结果，不是已观测的RS 4 Mini行为。

离线助手`activation_version_ack_view`只接受显式版本查询上下文的明文ACK原始payload：

| 原始payload | 条件视图 |
|---|---|
| `00` | 返回码成功，业务不完整，版本为空 |
| `00 00` | 源版本Ver1_0 |
| `00 03` | 源版本Ver1_3 |
| `00 33` | 源版本Ver13，与Ver1_3不同 |
| `00 64` | 显式源OTHER枚举，不代表目标版本支持 |
| `00 FE` | 保留原值254，已知版本为空，独立记录源find回退OTHER |
| `01 01` | COMMON返回码失败，保留完整业务体，不解析为Ver1_1 |

缺返回码、密文/无效flags、非ACK拒绝。额外业务字节保留；不模拟源共享单例或旧缓存，不生成DUML帧，不提供SDK接口。该助手没有请求关联器，不可用来自动解释所有00:32报文。激活状态业务首字节并不必然是版本，必须由具体请求上下文决定解释方式。

## 八段直接调用扫描

限定所有invoke指令的目标owner为DataCommonActiveGetVer，找到7个方法：2个在查询类内部，5个在FlightController、RC、Battery、Camera抽象中。外部匹配方法未见GIMBAL的DeviceType静态字段字面引用。字段引用只是局部线索，没有做跨方法参数数据流；这不能证明没有GIMBAL查询或固件不支持，反射/间接调用仍未排除。没有新增相机接口。

源setRecData支持GIMBAL分支并可能更新激活单例的版本，但“能处理该设备类型”与“HG724实际调用并获得有效响应”是两件事。当前仍无后者证据。

## 复现与完成门槛

```sh
PYTHONPATH=work/research/analysis-libs:tools/research work/python312/bin/python tools/research/ronin_activation_receive.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/prefix-restored-final-b \
  --output work/research/reproduced-activation-receive.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_activation_receive.py -v
```

两个独立真实输入提取结果须一致。测试覆盖全256版本/返回码/flags域、短业务体、未知枚举、输入快照和源构造/缓存赋值顺序，以及八段输入哈希和未验收边界。

实际扩展表/会话、HG724查询入口、严格请求关联、设备接受和激活/绑定/持久化仍未完成；没有激活发送、自动重试、网络请求或高级组合新增。清单仍49项，inventoryComplete及advancedDevelopment.allowed保持false。此前ACTIVATION.md的“包层尚未独立核对”由本次基础表条件证据补充，不提升为本机协议验收。

验收结果：最终工具对真实固定输入独立提取两次，39方法/7调用方法的JSON逐字节一致；新增13项研究测试，两Python环境研究各484通过。统一离线回归与类型/边界/原生签名构建通过，运行时代码和安装包未变。
