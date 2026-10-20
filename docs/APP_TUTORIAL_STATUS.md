# 教程状态被动候选

> 0.7.39：本页对应的App来源公开状态入口、缓存和事件已移除。以下仅作历史协议研究；见[清理范围](SDK_UNVERIFIED_REMOVAL.md)。

0.7.32 / 原生0.3.32 build35。证据来自固定Ronin 2.2.2 APK的[既有28方法审计](../tools/research/TUTORIAL.md)及[指纹](../protocol/research/ronin-tutorial-evidence.json)。通用类的布局不等于HG724实际布局或固件支持；六段恢复视图未找到类外直接调用者，不据此判断不支持。

## 接收与入口

应用仍只使用RS4Mini／RSGimbal。显式选择ronin-2.2.2来源后，被动处理sender4→receiver2、命令集04/命令2B、合法未加密请求型通知；拒绝ACK、加密、非法flags和不足5字节体。Node/Web的tutorialStatus、Python的tutorialStatus／tutorial_status、原生appTutorialStatus返回独立快照；kind=tutorial通过既有App状态观察者分发。关闭来源、切换来源或断线清空，坏帧保留此前有效缓存。JS/Python深复制；原生嵌套字典不可变。同步/异步观察者异常与设备处理隔离。

## 字段

| 字段 | 来源与语义 |
|---|---|
| rawStep | payload[0]，uint8，不夹取 |
| knownSourceStepName | 仅0..10有源名称，否则null |
| sourceFindResult | 源find的结果；未知步骤回退STEP_FINISH，不能表示完成 |
| rawCompletionWord | payload[1..4]小端uint32，保留最高位 |
| sourceSignedCompletionWord | 同一32位的Java有符号视图 |
| unknownCompletionBits | rawCompletionWord & 0xfffffe00 |
| sourceFlags | 下表九个getter，值为数值0/1 |
| sourceStepStatus | 源getStepStatus算术视图，布尔值，移位为(value-2)&31 |
| bodyHex / trailingHex | 完整业务体／第5字节以后的未知尾部 |

sourceFlags依次为bit0 getIsUnlock、bit1 getIsUpright、bit2 getIsFollowFinish、bit3 getIsStickFinish、bit4 getIsLockDirectionFinish、bit5 getIsRecentFinish、bit6 getIsSelfieFinish、bit7 getIsHandlePushFinish、bit8 getIsAppControlFinish。保留源拼写Recent，不修正为新的协议名。

源步骤0..10依次为STEP_FINISH、STEP_START、STEP_UNLOCK_GIMBAL、STEP_HOLD_GIMBAL_UPRIGHT、STEP_FOLLOW、STEP_STICK、STEP_LOCK_DIRECTION、STEP_RECENTER、STEP_SELFIE、STEP_PUSH、STEP_APP_CONTROL。sourceStepStatus中FINISH与START因Java移位回绕分别查看bit30/31；这两个算术结果不解释为教程生命周期或物理完成。高位仍同时保留在unknownCompletionBits。

deviceVerified、modelLayoutVerified、requestAssociationVerified、physicalCompletionVerified均为false。缓存不与传感器校准、其他程序状态、姿态或关节合并；通知不完成任何查询、校准等待或moveTo。

## 边界与验收

没有04:2C步骤发送、查询、订阅、自动ACK、自动推进或高级任务。04:2C通用类的int窄化成byte已静态核对，但HG724入口、合法步骤、作用及恢复未知，不开放发送。

共享八组离线向量由既有研究工具核对；测试覆盖256种步骤、32个单独置位、未知高位/尾部、短包、密文/ACK、缓存复制、来源/断线清理及查询/运动隔离。浏览器测试覆盖无Buffer环境，原生使用假设备；不操作真实硬件。实际通知、型号布局和物理效果仍需现场验收，48项清单与两项完成门槛保持未通过。
