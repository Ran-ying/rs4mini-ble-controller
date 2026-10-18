# 校准入口的型号、版本与动作条件

固定Ronin2.2.2/7096 APK与恢复代码bank03/05，只读审计63个方法指纹与2个布局资源。证据 `protocol/research/ronin-calibration-entry-evidence.json`；没有加载/执行App、线程、界面或硬件，不提供SDK接口。

## 路径与名称分离

UIViewManager.ViewIndex.SystemStatus的布局res/Z_.xml根为ConfigSystemStatusView。其initData在mViewList存在时创建ConfigNewSettingsView；TabViewPagerBaseView构造器初始化列表，onFinishInflate先虚调用initData再initView安装适配器。内部inflate布局res/je.xml根为merge。这证明条件化资源/构造链，不证明实际Activity挂载、选中项或现场点击。

| 页面动作 | 方法链 | 请求 |
|---|---|---|
| 普通校准 | systemCalibration → startCalibration | DataGimbalAutoCalibration/04:08，GYRO=5，业务05 |
| 高级校准 | advancedCalibration → startAdvancedCalibration | 同一04:08，AUTO=0，业务00 |

字段CALIBRATION_PART_NORMAL/ADVANCED分别绑定GYRO/AUTO。确认对话框的动作监听器11/13分别调用上述方法；两条动作方法都读取缓存MotorEnabled并要求toBool为真，否则只显示提示。可见性与方法内电机条件是不同层，不能因普通入口隐藏就宣称固件不支持GYRO。

页面名为systemCalibration的方法不调用system_calc/index36。已有SDK的sendAutoCalibrationRequest沿RoninBase.startGimbalAutoCalibration→04:0F/参数36路径；两者不得按名字合并。厂商页面的“高级校准”也是原生命令动作名称，不是本项目新增高级主机组合功能。

## HG724条件分支

两个来源必须分开：DeviceSwitchTextView使用mIndex/items中所选项的Model；CommonUtils.isOldSupportDevices经升级工具读取产品缓存ModelName，其GimbalComponentType形参并非此处的实际型号输入。

- 选中项第二代HG702/HG710或第三/四/五代时，高级入口直接显示，不发起版本回调分支。HG724属于第四代，与HG704/HG714一起。
- 普通入口仅在缓存ModelName属于RONIN2、RONINS、RONINSC、HG702/HG710、HG703/HG711/HG720时显示。isHG701实际比较RONINSC，不能按函数名猜缓存枚举。
- 显式假设所选项Model=HG724且缓存ModelName=HG724：普通隐藏、高级显示且不读取IMU版本。该假设不证明两者当前值、一致性或缓存新鲜度。

离线visibility_case要求分别给出selected_model和cached_model；这些字符串代表源码枚举名，不是BLE广播名、线上字段或本机读数。未知的版本结果保留为待观察，不自动当成功或失败。这是指定源码分支的静态视图，不是完整Java/Android调度或UI最终状态模拟器。

## IMU版本与异步边界

其他所选设备走checkIMUVersion回调；成功回调post后调用supportAdvancedCali，失败回调隐藏入口。阈值声明于实现接口ISupportedVersion，由其clinit调用CommonUtils.formatVersion计算，非本视图字段的编码常量。

阈值00.02.32.25：各分量按十进制parseInt，以value*256+part折叠为139289；比较严格大于，等于阈值不通过。离线canonical_version_number只覆盖规范无符号十进制分量输入，按Java int32分量范围与long溢出处理，不冒充全部Java字符串规则。

回调异步post，可见性分支不能证明没有旧回调覆盖或缓存变化。源码时序/竞态是否实际出现未观察，liveVisibilityVerified和相关时序标志均false。

## ACK、60秒计时与状态

普通请求的onSuccess为空；高级请求成功回调启动60000ms本地Rx计时器。计时器onNext直接调用的只有清理计时/关闭进度/显示提示，没有直接调用协议模型；这不证明固件已中止或全局没有其他路径。transitiveFirmwareStopProven保持false。

30 PROCESSING事件设置本地mAdvancedCalibrating并以getProgress整数加“%”显示；COMPLETE清本地标志、关闭提示/计时并显示完成。08响应则用另一套状态枚举。页面本地标志/显示不是每请求ID或序号关联，也不是物理完成证据。SDK0.7.28仍保留原始进度和progressUnitVerified=false，不因源UI后缀自动升级为本机单位验收。

## 复现与门槛

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_calibration_entry.py --apk work/research/dji-ronin-2.2.2.apk --bank-dir work/research/code-banks --output work/research/ronin-calibration-entry.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_calibration_entry.py -v
```

APK和bank03/05哈希在导入可选解析器前校验，资源解析只读且不inflate。13项测试覆盖HG724条件、独立选中项/缓存、代际组、版本严格边界/规范域/溢出、缺版本结果、电机与可见性分离、阈值生产链、缓存枚举别名、哈希先验与证据限制。

完整Activity可达性、现场身份/缓存、运输地址、请求关联、固件接受/作用/物理中止未完成。没有新增SDK收发、相机/视觉/高级功能；运行时/安装包仍0.7.28/0.3.28，全命令与高级新增门槛false。

最终固定输入独立提取两次，完整JSON逐字节一致。Python3.8与3.12研究工具各355项通过；统一离线Node241/Web23/Python217/原生637+247+3及类型/边界/构建通过。
