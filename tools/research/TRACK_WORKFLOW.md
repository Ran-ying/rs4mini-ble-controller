# 主页面挂载与轨迹界面工作流

2026-10-18，运行时/安装包仍0.7.21 / 原生0.3.21。新增只读`ronin_track_workflow.py`，
[证据](../../protocol/research/ronin-track-workflow-evidence.json)含29方法指纹、2个挂载布局。
依赖[入口审计](PROGRAM_ENTRY.md)的固定APK/bank03/05校验与条件分类，不执行App、Android inflate或BLE。

## 主页面到程序菜单的静态挂载

在前置Ronin2路径为false、手持缓存路径为true等源条件下，showMainView选择MainRoninNew。
其编译期布局2131558933对应res/EP.xml，实际包含CreateMainJumpEntryView。
该控件onFinishInflate调用initView，后者inflate布局2131558843，对应res/g3.xml。
子布局实际控件是RoninCreateJumpTextView，id=0x7f0a0313，与CreateRoninNew的viewId相同。

这个子类继承RoninJumpTextView，onClick先记录SMART_SHOOTING，再invoke-super父类onClick；
并没有额外替换程序路由。入口父控件自己的点击转交子控件onClick。
结合原入口审计的findByViewId、菜单按钮及程序根布局，所选静态资源/声明链已补齐。
这不是已执行界面、实时产品缓存或本机固件支持证明；动态挂载、可见性和源缓存条件仍需分别验收。

## 轨迹预览请求与ACK后的UI状态

CreateTrackView.previewToggle的IDLE分支设置recordOrPreview=1、phase=0、tripod=true，追加路点后调用04:62源类。
PREVIEWING分支设置recordOrPreview=1、phase=1。请求体与数值转换仍按[PROGRAMS.md](PROGRAMS.md)。

启动回调$12.onSuccess只post到AssistUIHandler，$12$1.run把mStatus设为PREVIEWING并updateUI。
停止回调$13同样post，run把mStatus设为IDLE、更新触点/UI。所选onFailure记录日志。
因此“ACK后界面显示预览/空闲”不能当成电机已开始/停止、路点已到达或整个程序完成。
本工具没有执行回调，也没有将这些UI状态接入SDK运动完成逻辑。

## 状态订阅与看门狗

onAttachedToWindow注册EventBus，初始化界面后调用checkGimbalStateStart；它通过04:6B、tag62请求StartContinuePush。
checkGimbalStateStop使用StopContinuePush；这是停止状态推送，不是04:62的停止程序。
openPushEnable/closePushEnable还涉及PushEnableYaw/Pitch缓存键，它们与6B订阅分开，不因名字相近而合并。

所选onEvent3MainThread直接读取共享DataGimbalGetPushExternalStatus的track getter。
该方法没有直接调用getCmdId、isSuccess或序号getter；此前源解析又会保留其他程序字段，
所以不能把任意该类型事件当本次轨迹的新状态。这里只说明所选方法的直接调用，不声称整个App无外层过滤。

源状态255走提示/空闲清理并提前返回；0、1、2参与与前状态的条件判断和UI更新。
未把这些数字发布为SDK物理完成枚举。源前状态、mInit、hardStop等条件不能抹掉。

普通处理末尾移除并重新安排message4，延迟3000ms；handleMessage的message4调用checkGimbalStateStart重新请求持续推送。
它不是轨迹超时停止或自动急停。另有1200ms的UI解锁定时，不能当作协议ACK超时或物理结束。

## 相机边界与未完成项

startRecord包含Ronin2分支的相机START_RECORD，以及手持分支的程序启动；停止/状态处理中也有相机STOP_RECORD分支。
预览请求有单独源值，但所有间接回调、固件行为和相机隔离尚未完整验证。不能把整个App录制工作流移植进非相机SDK。
本批没有新增相机接口、程序发送、高级运动或运行时版本。

后续仍需参数单位/参考系、完整型号条件、BLE接收头/返回码、请求关联、相机隔离、
固件执行/停止/断链效果与设备实测。全部命令与高级新增门槛保持false。

## 复现

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_track_workflow.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/code-banks \
  --output work/research/ronin-track-workflow-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_track_workflow.py -v
```

挂载资源保留原AXML哈希，不输出厂商完整布局/反汇编。手写提取只核对所选声明与直接调用，非完整符号执行。
共享view_literals新增显式选择参数，默认行为保持原4布局证据不变；不会通过修改全局选择改变旧研究结果。
