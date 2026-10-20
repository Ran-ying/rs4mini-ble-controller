# 程序菜单与HG724条件分类

2026-10-18，22方法指纹、4个真实APK布局。只读工具`ronin_program_entry.py`，
[固定证据](../../protocol/research/ronin-program-entry-evidence.json)。没有加载App类、执行反射、inflate布局、连接硬件或新增SDK发送。
运行时/安装包仍0.7.21 / 原生0.3.21，全部命令门槛false。

## 已补齐的条件链

产品抽象的PlatformType switch中HG724对应case9；这不是ordinal、设备类型103或线上字段。
`isHandle`的case9直接返回1；`getModel`的同一case直接返回Model.HG724。
工具读取packed-switch真实相对目标，并核对目标处的直接返回，不根据源码排列位置猜目标。

`updateProduct`在产品/显示器分类更新分支调用isHandle，写入IsHandleDevice缓存键。
存在上次类型相同的提前返回，以及未知型号分支，不能据此宣称每次调用都会刷新为true。
UI的CommonUtils.isHandheldDevice读这个缓存键并toBool；其GimbalComponentType参数没有用于查询型号。
UIViewManager.showMainView依次检查Ronin2、手持缓存/Focus，手持条件分支选择MainRoninNew。
源条件链更完整了，但实际平台发现、缓存新鲜度和完整主页面挂载仍待验证。

## 真实菜单资源

| ViewIndex声明 | 原APK布局 | 根类 |
|---|---|---|
| CreateRoninNew | res/j9.xml | UIStageView |
| CreatePanoRonins | res/sm.xml | CreatePanoramaView |
| CreateTrackRonins | res/Kr.xml | CreateTrackView |
| CreatePathDelayRonins | res/Nt.xml | CreatePathDelayView |

ViewIndex构造的名称、ordinal、viewId、layoutId来自编译期常量；parentId不在本批解析范围，不伪造值。
4个资源各只有一个所选配置，记录原始AXML哈希。主菜单真实包含上述三个程序的RoninJumpTextView id，
布局根类也已读取；因此不是只凭类名相似或枚举存在建立关联。
MainRoninNew到CreateRoninNew的完整挂载/可见性、其他布局配置和运行时入口仍未审完。

RoninJumpTextView.init通过自身id→ViewIndex.findByViewId；showSubView→showNext→UIViewManager.showView，后者按资源id inflate。
程序类的请求体/直接调用研究沿用[PROGRAMS.md](PROGRAMS.md)，不能把菜单资源本身当作已发送协议证据。

## 两个容易误判的地方

1. CreateMainJumpEntryView附近HG724 case9用于getProductParamForCableCapabilityUrl；
帮助按钮把product_name交给ShutterCableCapabilityActivity。它是快门线帮助路由，不是程序型号支持证明。
2. RoninJumpTextView含checkIsValuableForCreate辅助方法，检查连接、电机缓存和isConnectShutter；
但本次所选onClick直接调用的是isAffect3DRoll360、checkCreateIsWorking与showSubView，没有直接调用该辅助方法。
不能把“找到一个检查函数”写成“点击入口一定受它保护”。间接调用/回调/其他入口未全部审计，不宣称完全无快门检查。

checkCreateIsWorking使用CreateCameraManager的isWorking和mWorkingCreateMode等缓存决定是否弹窗；
这些App缓存不是固件动作完成/取消证据。相机/外设隔离仍未完成，不由此开放程序发送或高级组合。

## 复现

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python \
  tools/research/ronin_program_entry.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/code-banks \
  --output work/research/ronin-program-entry-reproduced.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_program_entry.py -v
```

APK及bank03/05哈希在可选解析器加载前验证。小型解析器只读所选HG724赋值模板及有限常量，不模拟全部DEX/Java执行。
方法指纹、资源事实和局部条件分支不能代替完整CFG、异常/动态Map、固件接收与物理测试。
后续仍需主页面挂载、型号/预设条件、单位/参考系、相机隔离和执行/停止/通知关联证据。

## 后续：八段程序重审（2026-10-20）

见 [PROGRAM_PREFIX.md](PROGRAM_PREFIX.md)。
