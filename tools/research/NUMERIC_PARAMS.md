# 跟随/摇杆数值参数与独立配置分支

2026-10-16，运行时仍0.7.9/原生0.3.9。本批为只读静态证据与可复现工具，尚未新增这18项数值SDK接口，不发送或执行厂商代码。

## 普通命名参数

| 参数 | Pitch/Roll/Yaw索引 | size | typeID | 源码范围 |
|---|---|---:|---:|---|
| 跟随speed | 3 / 12 / 2 | 2 | 1 INT16U | 1..100 |
| 跟随acceleration | 15 / 16 / 14 | 2 | 1 INT16U | 1..100 |
| 跟随deadZone | 5 / 13 / 4 | 2 | 1 INT16U | 0..100 |
| RC speed | 42 / 43 / 41 | 2 | 1 INT16U | 0..100 |
| RC deadZone | 27 / 40 / 26 | 1 | 0 INT08U | 0..100 |
| RC smoothing | 9 / 39 / 8 | 2 | 1 INT16U | 0..30 |

共18条，资源名字唯一；每一项通过实际枚举/命令映射查名字，再读取资源，未按索引反推字段。这些是厂商原始整数，不声明百分比、度/秒或机械安全范围。

RC九项由Ronin2 setter查mCacheKeyCommandParamMap，解析initCommandCapabilityMap中的无条件键→BaseCommand映射，再进入setRonin2CommonUserParam/普通04:0F。跟随Roll三项直接用命名键走该路径；Pitch/Yaw六项沿实际继承解析到Aircraft setter，经SettingParamCmd.getCmdString和通用setParam进入DataGimbalSetUserParams。不能仅看同名抽象类或父类的旧索引数组来选择路径。

枚举有些构造器未显式传数据模型类，但会设置mPushClazz=DataGimbalGetUserParams；不是空模型，也不能据Ronin2类名改用04:32。标准04:10读取编码可应用于这些显式index/size上下文；不声称每个setter本身先发读取。

## 类型与字节顺序

已核对TypeId.INT08U=0、INT16U=1，DataGimbalSetUserParams合成switch分别映射case4/5；单项和数组两条doPack分支均经Number.intValue→BytesUtil.getBytes(int)，再按资源size复制。低字节先写，第二字节取掩码ff00后右移8；类型ID与实际资源宽度分开核对。

例如普通Pitch跟随speed=100的候选写体03 02 64 00，RC Pitch deadZone=100为1b 01 64；它们只是依据源码编码得到的离线字节，不是已发送抓包或硬件验收结果。

## 档位、数值、当前预设分别处理

0.7.9已实现的custom/low/middle/high是每轴两位档位，不能当作上述数值本身。Pitch/Yaw通用跟随setter还检查isCustomAdvancedSettingProfile，该检查依赖App当前推送的presetID；范围合法不代表该预设已激活。后续SDK不能自动宣称custom档位/预设成立或偷偷切换模式。继承、源码范围、ACK与实际效果须分别验收。

## 独立配置不能套用普通RC字段

CreateVideoViewModel.perform*Set根据supportProfileStandalone选择另一条路径；该条件涉及设备类型及部分型号IMU版本。不能用字段名相似或本机型号身份代替分支证据。

| 独立配置参数 | Pitch/Roll/Yaw索引 | size / typeID | 源码范围 |
|---|---|---|---|
| gimbal_create_smooth_* | 77 / 76 / 78 | 2 / 0 | 0..30 |
| gimbal_create_max_speed_* | 80 / 79 / 81 | 2 / 0 | 0..100 |

这些记录typeID0但size2，进一步说明不能只看INT08U名称就截成一个字节。

该UI分支调用DataGimbalSetUserParams.setIndexs/setValues，一次请求将gimbal_input_source/index72/size1写2，再写所选数值参数。已追到六个调用方和公共打包方法；这不是证明固件强制要求此组合，也没有证明在本机切换输入源的效果。不得把上述字段当普通RC参数别名、自动选路，或省略输入源后声称复刻了App分支。

## 复现与范围

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_numeric_params_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --sdk work/research/code-banks/business-05-code-restored.dex \
  --ui work/research/code-banks/business-03-code-restored.dex \
  --output work/research/reproduced-numeric-params.json
```

[证据JSON](../../protocol/research/ronin-numeric-params-evidence.json) 含18条普通命名记录、独立配置6条与输入源记录、有效继承路径、类型/分支及42方法指纹。工具固定APK与两段恢复视图哈希，核对实际寄存器绑定，遇到映射歧义或条件分支不猜值；输出不含完整厂商方法体。

标准库研究测试在Python3.8/3.12各53项通过，固定APK复现一致。没有SDK发送扩大、扫描、连接、运动、实时UI或App代码执行。型号/预设条件、数值SDK接口、本机效果/持久化、输入源选择等仍待完成；全协议和高级门槛保持false。

后续0.7.10已封装18项普通数值SDK，当前范围与活动预设未验证边界见 [APP_NUMERIC_TUNING.md](../../docs/APP_NUMERIC_TUNING.md)。独立配置输入源组合仍未封装；本工具本身不提供SDK或发送能力。
