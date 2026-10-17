# 参数订阅与预设推送的包层审计

2026-10-17，运行时保持SDK0.7.11 / 原生0.3.11。本批只提供静态证据、离线请求体核对与预设字段检查，不构造DUML帧、不导入SDK/UI、不发送或操作设备。

## 04:12订阅

DataGimbalSubscribeParams.start选择APP→CENTER，receiverId=7，不请求ACK，命令04:12。DeviceType.CENTER=5，经标准SendPack字段打包，接收字节为(7<<5)|5=E5；这是源码字段与打包事实，不是本机实际链路观测，后续路由/固件兼容仍未验证。不能直接复用当前02→04、等待ACK的参数查询。

每个命令组由commandByte、最高频道号、LSB优先位图组成。第二字节是list.size()-1，即最高保留频道号，不是位图字节数；位图长度ceil((最高频道号+1)/8)。多组来自HashMap迭代，没有稳定顺序保证。

| 命令组与频道 | 离线单组请求体 | 含义与边界 |
|---|---|---|
| 10 / 0 | 100001 | UserProfile/table_choice的订阅，和固定04:24预设推送不同 |
| 32 / 0 | 320001 | Pitch电机刚度，频道同为0但命令空间不同 |
| 24 / 0,2,9 | 24090502 | 只验证跨字节位图算法，不证明三个频道是型号支持或业务字段 |
| 空频道集合 | 空体/省略该组 | 本地组移除结果，不是已验证的远端停止请求 |

BaseCommand可能使用显式mId，或在缺省构造中读命名参数index；枚举ordinal不是频道。例如USER_PROFILE的ordinal12、显式频道0、命名table_choice要分别保存。put按getPushClazz区分普通GetUserParams/10和RoninGetParams/32，再取getId。HG724恢复的继承链中mSubscribeController赋值点仍为Ronin2构造，不把类名Ronin2单独当作本机支持。

## 刷新与取消

Ronin2SubscribeIMPL每1秒检查远端/连接和非空订阅表，再刷新请求。本地按命令+频道引用计数，callGetValue临时增加引用并在3000ms后提交移除；3000ms是App本地临时读取生命周期，不是已确认固件TTL。unsubscribe把指定位清零、裁掉末尾零位，空列表从map移除；最后一个组移除后hasChannelSubscribed使刷新停止。

这些操作没有证明远端立即停止推送、租期长度、断线残留状态或其他控制端之间的隔离。因此尚未开放持久SDK订阅或宣称unsubscribe已经完成。destroy关闭本地执行器也不等于固件停止。

## 04:24预设字段

当前App命令枚举把04:24分派至DataGimbalGetPushUserParams。RecvPack对请求型消息从帧偏移11提取payload，不剥离首字节返回码；ACK型需要时会把第11字节当返回码并从12取业务体。DataBase.setPushRecPack→setPushRecData→setRecData把数据原样保存，DJICameraDataBase与该推送类没有覆盖这些方法。getPresetID最终读偏移2、宽度1。

因此，对已明确为未加密、请求型04:24的源码路径，可以把payload[2]解释为源MovementSettingsProfile原值。不能对ACK应用同一偏移，不能对短帧补零，不把它等同table_choice、PF/PTF编号或本机活动预设确认。本批离线检查保留未知值；deviceVerified和activePresetVerified仍false。此前PROFILES.md的“包层尚未追通”由本节在这个严格范围内补充，目标设备报文依旧未验证。

## 复现与剩余项

ronin_subscription_trace.py固定APK与恢复bank05哈希，核对34个方法指纹、端点、位图、本地管理器和接收包层。ronin_subscription_payloads.py只有离线单组body与请求型预设字段核对，不编码完整帧。证据为protocol/research/ronin-subscription-evidence.json。

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_subscription_trace.py --apk work/research/dji-ronin-2.2.2.apk --dex work/research/code-banks/business-05-code-restored.dex --output work/research/subscription-reproduced.json
```

新增边界覆盖位图7/8/255、重复频道、错误命令/频道、空集合、ordinal与显式ID、短推送、ACK/加密消息、未知预设及未解析构造/控制流。SDK接口和全部频道业务语义、本机路由/刷新/停止仍待补齐；无硬件、实时UI或厂商代码执行，两个完整性门槛保持false。
