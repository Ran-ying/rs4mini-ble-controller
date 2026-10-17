# 原生角度控制：04:0A 与 04:14

2026-10-17。固定 Ronin 2.2.2/7096 APK 与六段恢复视图，48 个方法指纹见
[证据](../../protocol/research/ronin-angles-evidence.json)。仅静态阅读；未执行厂商代码、发送命令或操作硬件。
运行时仍为 0.7.19 / 原生 0.3.19，本批没有新增发送接口。

## HG724 继承路径

HG724→HG702→Ronin2→RoninBase→Handheld→X3→Aircraft→DJIGimbalAbstraction。
本链只有最后的基础类定义 `rotate(InnerCallback, Rotation)`，没有子类同名覆盖。
它的 ABSOLUTE_ANGLE 和 RELATIVE_ANGLE 分支均使用 DataGimbalAbsAngleControl（04:14）；
SPEED 是另一个分支，使用 DataGimbalSpeedControl，不能把整个 rotate 等同角度请求。

这建立的是静态方法解析路径。轴能力初始化、调用入口的完整可达性、固件支持和坐标参考系尚未验收。
基础方法先检查 Rotation/模式及请求轴的 capability；绝对角还检查 capability 的最小/最大值。
这些能力值不能由协议类或其他型号的限制替代。

## 04:14 源请求体

| 偏移 | 字段 |
|---|---|
| 0/2/4，各2字节 | yaw / roll / pitch，signed int16 LE |
| 6 | bit0 controlMode；bit1/2/3 分别为 yaw/roll/pitch Invalid |
| 7 | overtime，源 int 取低8位 |

角度分支先清零三轴；未指定轴通过 Float.MAX_VALUE 哨兵识别，并设置 Invalid=true。
指定轴使用 float32 角度乘 float32 的10，再 float-to-int 向零截断、int-to-short 窄化。
这与先截断角度再乘10不同。指定轴的绝对分支 controlMode=true，相对分支 false；初始值为true，全部轴均未指定时不能据此宣称相对控制位为false。
源 double time 先限制到 0.1..25.5，再乘10转 int，传入 overtime；记录的是源数值换算，
不据此承诺固件执行时长、到位精度、物理角度参考系或可碰撞范围。
离线帮助函数仅接受有限数值，不模拟源 NaN/Infinity 等异常路径。

源 start 请求 ACK，但 rotate 使用没有业务回调的 start() 后立即 onSuccess(null)。
因此源上层成功不是“等到 ACK”，更不是“到位”。不把这个行为复制为 SDK 的物理完成承诺。

角度和速度分支均先调用 justSendPauseData()：新建
DataSingleSendAppStateForStabilization，设置 GimbalState.START 后 start()。
这不是现有主机三帧中位 stop，也不能凭函数名推断固件暂停/恢复效果。
接收 ID 来自 getReceiverIdByIndex→DoubleCameraSupportUtil.getGimbalIdInProtocol；
该映射、包层传递与暂停/恢复链仍需审计。本批不据此开放当前 App 原生角度接口。

## 04:0A 是两种不同的10字节布局

| 字段 | DataGimbalAngleControl | DataGimbalSetAngle |
|---|---|---|
| 0/2/4 | yaw/roll/pitch signed short LE | yaw/roll/pitch int 取低16位 LE |
| 6..7 | allowDeviation short，构造默认300 | mErrorValue int 取低16位，默认10 |
| 8 | 连续移位、相加、byte 窄化，见下文 | `(mRef << 5) \| 192` 的低字节，mRef默认0 |
| 9 | overtime 的低字节 | timtout 的低字节，默认2 |

AngleControl 标志的固定指令不是常见的逐位 OR：先由 permission/reference 得到0..3，
左移6、加absolute、再左移5并窄化；之后依次加 yaw-valid 左移4窄化、加 roll-valid
左移3窄化、加 pitch-valid 左移2窄化。按这些静态整数规则，最终保留
`(rollValid << 5) | (pitchValid << 2)`；三轴 valid 默认 true 时为0x24。
这只是当前固定方法的算术结果，不能宣称厂商 bug、固件忽略其他字段或已验证线上包。

SetAngle 的两个 start 重载也不同：callback 重载使用存储的 receiverType/receiverID；
带 timeout/repeat 参数的重载固定 GIMBAL，并设置 SendPack.timeOut/repeatTimes。
传输层 timeout 与 payload 的 timtout 字节是不同字段，不推定相同单位。
两类 setter 直接存入原始整数/short，不从方法名推断角度单位或安全范围。

六段扫描仅发现两处类外直接调用，均在 bank05 的 DJIDT501Abstraction：构造及
setUvcCameraGimbalMotion，使用 DataGimbalSetAngle；没有找到 AngleControl 类外直接调用。
UVC/相机功能在用户排除范围内，不新增相关接口。没有定位 HG724 的 0A 路径；
零引用不能证明设备不支持，未恢复 banks1/7、保护桩、反射和动态路径仍未排除。

## 复现与边界

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_angles_trace.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/code-banks \
  --output work/research/ronin-angles-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_angles_trace.py -v
```

工具先校验所有输入哈希，再加载可选解析器。输出方法指纹和引用，不保存厂商反汇编。
语义来自对这些固定方法的人工静态核对，工具执行关键引用/常量检查，不是通用 CFG 证明器。
手写纯函数仅复现原始字段/数值窄化，不构造 DUML、不导入 SDK、不发数据。
测试覆盖固定字节向量、符号/轴序、16种无效轴位、64种0A布尔组合、float32舍入和截断、
时间限制以及输入哈希预检；不是硬件验收。

下一步：能力初始化与接收地址、暂停/恢复关联、ACK/错误与完成/中止语义，然后完成受控 SDK
封装及本机验收。现有 moveTo 仍是电脑组合速度+关节反馈，不改用这些候选命令。
全部命令清单完整性及高级新增门槛继续 false。
