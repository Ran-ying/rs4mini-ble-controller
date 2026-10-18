# 平衡入口的所选型号条件与旧调整页资源

2026-10-19。继[04:40业务审计](BALANCE_ADJUST.md)后，固定APK/六段恢复DEX继续核对导航、型号分组、四个视图映射和三个独立布局。工具[ronin_balance_entry.py](ronin_balance_entry.py)，证据[ronin-balance-entry-evidence.json](../../protocol/research/ronin-balance-entry-evidence.json)。不运行UI、APK或Java/JNI，不打开视频/网页，不新增SDK收发；运行时保持0.7.32/0.3.32。

## HG724明确所选项的菜单分支

BalanceCheckJumpEntryView.onClick调用DeviceSwitchTextView.isNeedBalanceTestDeviceIndex：它读取items[mIndex].model，而不是从BLE查询本机身份。以下只讨论索引有效且所选项model已明确的源代码情形：

| 所选型号 | needBalanceTest | 菜单目标 | 视频页测试按钮 |
|---|---|---|---|
| RONIN2 / RONINS / RONINSC | true | ConfigSettingBalanceTestHG701 | VISIBLE0 |
| HG702 / HG710 | true | ConfigSettingBalanceTestHG701 | VISIBLE0 |
| HG720 | true | ConfigSettingBalanceTestHG701 | VISIBLE0 |
| HG703 / HG711 | false | GimbalVideoAdjustRS3 | GONE8 |
| HG704 / HG714 / **HG724** | false | GimbalVideoAdjustRS3 | GONE8 |
| HG705 / HG715 | false | GimbalVideoAdjustRS3 | GONE8 |

因此，**所选项明确为HG724且这次onClick被调用时，普通菜单分支绕过旧平衡测试页。** 这不是现场UI挂载、实际连接型号或固件不支持04:40的证明。测试条件函数只要求显式源型号名；不把103、任意数字索引或缓存缺失当HG724。源不同索引访问方法对越界的处理也不同，不能推广成统一默认设备。

SettingBalanceAjustView.onFinishInflate与onDeviceIndexChanged均以相同needBalanceTest条件控制mBtnJump2BalanceCheck。HG724的四个帮助分支选择RSC4命名的安装/三轴平衡网页入口；这里是源码资源/链接选择，不是相机控制、BLE校准或新的目标设备命令。本研究不请求这些链接。

## 视图名不等于类或能力

| ViewIndex | ordinal | viewId | layout资源 | 根类 |
|---|---:|---:|---|---|
| ConfigSettingBalanceTestHG701 | 16 | 2131362578 | res/jb.xml | SettingBalanceCheckView |
| GimbalAdjustHG701 | 38 | -1 | res/Wq.xml | GimbalAdjustView |
| GimbalVideoAdjustHG701 | 39 | 2131363405 | res/Ci.xml | SettingBalanceAjustView |
| GimbalVideoAdjustRS3 | 40 | 2131363405 | res/Ci.xml | SettingBalanceAjustView |

两个视频视图枚举不同，但viewId、layoutId和根类相同。GimbalAdjustHG701是另一个布局，不能因名称都包含Adjust而将HG724视频菜单连接到04:40发送类。资源与导航引用不是硬件协议命令编号。

在六段恢复视图中，GimbalAdjustHG701字段直接引用仅见于ViewIndex的$values/<clinit>及RoninGimbalOptionPageFragment.shouldRespondBackPress。字段读写和返回键逻辑不是发送或进入页面的证据。BeginnerGuideManager.next包含新旧视频选择和后续引导步骤，所读方法中未直接引用GimbalAdjustHG701。仍未排除未恢复段01/07、反射/动态路径、残余保护桩或其他类加载器，不能推断该页面永不可达或设备不支持该命令。

## 强制打开旧页时的可见性是另一件事

SettingBalanceCheckView.onAttachedToWindow在RONINSC或supportSince2ndGenDeviceIndex为true时显示调整说明。后者包括第二、第三、第四、第五代所选型号，所以**假如旧页已被其他路径打开，HG724会得到说明可见的条件**；这不能推翻普通菜单走视频页的结果。旧页的说明点击还跳到GimbalVideoAdjustHG701，不是GimbalAdjustHG701。

旧页startTestBalance在MotorEnabled缓存允许时发起StartBalanceTest动作键，与既有HG724继承的balance_test/index37、04:0F/10研究相接；不把该动作替换为04:40。普通菜单不展示旧测试页也不代表已封装的源参数事务得到实机确认，或固件不能接受该参数。

## 复现及边界

```sh
PYTHONPATH=work/research/analysis-libs:tools/research work/python312/bin/python tools/research/ronin_balance_entry.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/code-banks \
  --output work/research/reproduced-balance-entry.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_balance_entry.py -v
```

30方法指纹、4视图映射/3独立布局哈希及限定字段引用可复现；12项标准库测试覆盖所选型号分组、HG724条件路由、强制旧页与普通入口区别、共享布局、输入哈希及证据门槛。没有完整厂商方法/资源入库，没有SDK接口或硬件操作。

hg724Command40PathEstablished=false与hg724Command40UnsupportedProven=false同时保留。实际路由/会话、04:40包层与物理效果仍未知；48项清单和全部命令/高级开发门槛仍未通过。
