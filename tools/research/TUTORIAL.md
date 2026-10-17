# 04:2B/2C教程状态与步骤候选

2026-10-17。固定六段恢复视图，28方法指纹及外部调用检索见
[证据](../../protocol/research/ronin-tutorial-evidence.json)。只读研究，不执行厂商代码或操作硬件。
运行时/安装包保持0.7.21 / 原生0.3.21，本批没有新增SDK接口或发送。

## 源通知布局

GetPushTutorialStatus的wire值43（0x2B），绑定DataGimbalGetPushTutorialStatus。
业务偏移0/宽1是当前步骤；偏移1/宽4是little-endian Integer状态字，完整已知体至少5字节。
Java源Integer为signed32；离线工具另保留uint32原值、signed视图、未知高位和全部尾字节。

| 源getter（返回int0/1） | 状态字bit |
|---|---:|
| getIsUnlock | 0 |
| getIsUpright | 1 |
| getIsFollowFinish | 2 |
| getIsStickFinish | 3 |
| getIsLockDirectionFinish | 4 |
| getIsRecentFinish | 5 |
| getIsSelfieFinish | 6 |
| getIsHandlePushFinish | 7 |
| getIsAppControlFinish | 8 |

已知掩码为0x1ff，其他23位未知；不截成uint16或丢弃符号位，不把int getter擅自改成设备动作完成布尔。
这些是教程字段，不证明原生轨迹、回中、定位或取消完成。

## 枚举未知回退与Java移位

源枚举0..10依次为STEP_FINISH、STEP_START、STEP_UNLOCK_GIMBAL、STEP_HOLD_GIMBAL_UPRIGHT、
STEP_FOLLOW、STEP_STICK、STEP_LOCK_DIRECTION、STEP_RECENTER、STEP_SELFIE、STEP_PUSH、STEP_APP_CONTROL。
find(raw)找不到时返回默认STEP_FINISH，不会保留一个UNKNOWN枚举。
因此未知原值11/255经源getCurStep可以展示为“完成”，不能照搬成SDK设备完成状态。
离线帮助函数同时保留rawStep、knownSourceStepName=null与sourceFindResult=STEP_FINISH，明确区分原量与源回退。

getStepStatus(enum)使用`word >> (enum.value - 2)`再&1。
DEX/Java对int移位距离取低5位；STEP_FINISH/START的-2/-1分别实际选择bit30/31，
不是Python的负移位异常，也不是bit0/1。该公式是固定源码算术，不诊断厂商bug或推定这些调用有实际业务用途。
源码九个固定getter对应正常步骤2..10的bit0..8；不能用getStepStatus(0/1)代替教程生命周期或固件完成通知。

## 步骤请求候选

SetTutorialStep的wire值44（0x2C），setter接收Java int后int-to-byte，doPack发送一个低8位字节。
离线例：-1→ff，256→00，257→01；这些是源码窄化结果，不是安全参数或设备接受范围。
start为APP→GIMBAL、请求ACK、类声明不加密；包层地址/加密仍依通用路径，本机未验证。
成功ACK不能证明教程已执行或动作完成，0也不能当取消/停止。
工具只生成单字节离线候选，不构造DUML、不导入SDK/UI、不发送。

六段指令扫描没有发现这三个教程类的外部直接invoke。命令枚举Class绑定不等于业务调用。
未恢复banks1/7、残留保护桩、反射/动态/固件路径仍未排除，不能据零引用判设备不支持。
没有建立HG724实际入口、布局或2C效果/恢复路径；本批不把旧通用教程暴露为RS4Mini能力，也不新增教程发送。

## 复现与后续

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_tutorial_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/code-banks \
  --output work/research/ronin-tutorial-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_tutorial_trace.py -v
```

先校验所有输入哈希，再加载可选解析器；方法指纹和移位/窄化关键语法核对不是通用CFG或虚拟机。
未输出厂商反汇编，未安装/执行APK，没有扫描、连接或移动设备。
后续优先审计HG724支持键/动作注册及真实业务入口，不能只按继承或App枚举判断覆盖。
完整命令与新增高级功能门槛保持false。
