# 轨迹路点时间、角度来源与ActualPose

2026-10-18，运行时/安装包保持Node/Python/Web0.7.24、原生0.3.24 build27。本批不增加SDK发送或高级功能。
只读工具 `ronin_track_points.py` 校验固定APK与恢复bank03/05后提取51个方法指纹；不导入SDK、不构造DUML帧、不执行厂商代码或UI。
证据：[ronin-track-points-evidence.json](../../protocol/research/ronin-track-points-evidence.json)。

## 时间不是滑条原值

CreateTrackView的transferProgressToSecond先将float进度转int，再按以下规则换算：不超过60直接作为秒；超过60使用(progress-59)*60。
移动滑条范围1..159，因此1、60、61、159分别显示/存储1秒、60秒、120秒、6000秒；停留滑条0..60，回调直接截断为整数秒。
移动回调把换算结果写入moveTime，默认的移动和停留值均为2秒。整数秒到进度的反向换算在>60时使用seconds/60截断再加59，存在精度损失，例如121秒→进度61→120秒。
工具的slider_seconds只覆盖有限float32进度1..159，seconds_slider只覆盖1..6000整数；不是完整Java数值模拟或固件安全时长表。

JSON恢复构造器对moveTime只做Math.min(value,6000)，没有下限夹取；stopTime直接读取浮点。不能将界面滑条范围推广为所有恢复数据的保证。
通用04:62打包仍按float32乘10、Math.round和低16位，见[程序请求研究](PROGRAMS.md)；源码没有把UI范围变成机械或时序保证。

## 路点角度的来源链

所选声明链是：

`04:66通用枚举 → DataGimbalSetPushPeripheralStatus ActualPose getter → Ronin2抽象缓存通知 → PeripheralPosYaw/Pitch → 路径控件坐标换算 → onPointAdd → RoadPoint → 04:62 addRoadPoint`

CreateGimbalPathView订阅PeripheralPosYaw/Pitch，读取后经setCameraPosition把源角度转为屏幕网格；Track子控件从网格转换回角度。
路径控件还读取PeripheralPosRoll并作为第三个参数回调，但CreateTrackView.onPointAdd使用的RoadPoint构造器只接收Yaw/Pitch及两项时间，没有保存该Roll参数。
源UI将这些角度以°显示；这只证明源UI的单位约定，不证明本机参考系、零点、轴正方向或与现有04:05姿态/关节字段相同。

| 04:66命名空间中的源类型 | 明确mId（不是ordinal） | 源缓存键 |
|---|---:|---|
| PActualPose | 34 / 0x22 | PeripheralPosPitch |
| RActualPose | 35 / 0x23 | PeripheralPosRoll |
| YActualPose | 36 / 0x24 | PeripheralPosYaw |
| PMotorAngle | 16 / 0x10 | 本批仅核对独立getter，不绑定到上述ActualPose键 |
| RMotorAngle | 17 / 0x11 | 同上 |
| YMotorAngle | 18 / 0x12 | 同上 |

这里的编号是04:66内部DataType标签，不是04:0F/10参数索引，也不是其他命令号；不能跨命名空间混用。
ActualPose与MotorAngle在所选源码中明确分开。没有据此修改现有getJointAngles()/getAttitude()映射，也不能把moveTo目标直接转作固件轨迹路点。
所选父类缓存生产路径不等于运行时HG724实例/当前通知/固件支持；关系仍需目标型号与实机证明。

## 首点和Roll的实际发送参数

- previewToggle把保存的moveTime/stopTime/Yaw/Pitch逐点加入，Roll固定0。
- sendToDeviceStart先有一轮添加，随后clearPoint，再建立最终点队列；最终首点moveTime固定0，后续点取保存值，Roll始终固定0。
- 新建第一个UI路点本来也把moveTime设0，但JSON恢复可保留不同值。因此不能把预览路径与sendToDeviceStart的首点规则合并。

工具用局部寄存器来源窗口核对三种addRoadPoint参数排列；它没有执行循环或做完整符号执行。首次被清空的队列不当成第二次固件发送。
源单例队列、回调、记录/预览分支的差异仍需保留，不把通用三轴字段存在当作该UI完整支持三轴轨迹。

## 04:66记录和宽度

所选源setPushRecData先调用父层，再检查首字节是否1；为1时按tag、length、payload保存至共享map。
源tag和length来自有符号byte，未完整验长；其他记录及旧值会保留。源getter找不到记录时返回0，生产端仍可通知旧值或默认值。
离线peripheral_records只分析当前完整业务体，保留重复/未知记录和原始字节，不继承旧字段或补零。flag!=1时记录分支未选择，后续体保持不透明。
它不是SDK通知解析器，BLE原始偏移、端点和真实型号布局仍未验收。

六个已选getter均把getIntValue结果转float再除10。getIntValue按记录长度选择：1字节signed byte；2字节signed short LE；4字节signed int LE；8字节signed long LE后经intValue截为低32位。float转换发生在除法前，须保留float32舍入。
源还可走其他长度的Integer/fillBytes路径；本工具不猜其本机含义，已知标签的其他长度保持原始体、不生成值。源负长度高位>=128或截断记录拒绝。

## 相机、完成与剩余边界

previewToggle所选方法中未发现直接相机调用；该结果只限列出的直接调用，不能排除间接回调或固件触发，因此completeCameraIsolationVerified仍false。
未把ACK后的UI状态当物理开始/停止，未改变[轨迹工作流](TRACK_WORKFLOW.md)中的完成语义边界。
仍缺ActualPose的物理参考系及其与04:05的关系、完整型号路由、固件接受、相机隔离和执行/中止/断线效果。
本批没有程序执行/停止接口、04:66运行时新增解码、订阅变更或高级功能；完整命令与高级门槛保持false。

## 复现

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_track_points.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/code-banks \
  --output work/research/ronin-track-points-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_track_points.py -v
```

新增22项边界测试覆盖时间分段/float32/反向损失，ActualPose与MotorAngle分离、整数符号/宽度/窄化/舍入、未知/重复/缺失/截断记录、参数和通知寄存器绑定及哈希预检。
APK、恢复DEX及完整反汇编留在忽略目录，不进入Git；全部是离线源码与手写分析视图，无厂商代码执行或硬件操作。

## 后续：八段程序重审（2026-10-20）

见 [PROGRAM_PREFIX.md](PROGRAM_PREFIX.md)。
