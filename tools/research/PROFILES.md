# 用户配置、运动预设与工作模式的静态核对

2026-10-17，当前运行时0.7.16 / 原生0.3.16；下方早期研究保留历史上下文。本批新增只读审计与证据，没有新增发送、SDK接口或高级功能，没有执行厂商代码或操作设备。

## 三个概念不能共用枚举

| 来源 | 已核对事实 | 不能据此宣称 |
|---|---|---|
| UserProfile / USER_PROFILE | 普通用户参数table_choice，index0/size1，源码资源范围0..5；UI M1/M2/M3按钮写0/1/2 | 三个按钮分别就是本机PF/PTF/FPV，或资源全部值都已确认UI含义 |
| MovementSettingsProfile | CUSTOM_1=0、CUSTOM_2=1、FAST=3、MEDIUM=4、SLOW=5、UNKNOWN=255；通用custom数值setter检查前两项 | 与table_choice实时值等价，或设置custom档位就激活该预设 |
| GimbalWorkMode / GIMBAL_WORK_MODE | 普通参数ronin_gimbal_work_mode，index62/size1，源码范围0..128；枚举原名Free/Flower/Fpv/Center分别0/1/2/3 | 可把Flower改译PF/PTF，或把旧Ronin2工作模式枚举直接当本机跟随切换 |

两个普通命名参数都由DataGimbalGetUserParams处理。HG724沿继承链解析到Ronin2的setUserProfile/setGimbalWorkMode，再经setRonin2CommonUserParam范围检查、DataGimbalSetUserParams.setInfo。参数事件分别更新UserProfile/GimbalWorkMode缓存。此处是静态来源，不是本机读数、SDK接口或固件支持证据。

## HG724的新模式路径

App产品Model.HG724经CommonUtils.is4thGenDevice使isUseNewProfileDevice为true，选择setTrackModeHG711；名称中的HG711不代表该方法只适用于那个型号。设备选择列表中的Model.HG724同样被is4thGenDeviceIndex归入新列表。

| 下拉列表 | 默认语言条目顺序 |
|---|---|
| 旧0x7f030002 | Pan & Tilt follow、Pan follow、FPV、Custom、3D Roll 360 |
| 新0x7f030003 | FPV、Custom、3D Roll 360 |

不能把旧列表位置0/1/2直接照搬给HG724。新路径中的FPV分支先经缓存setter关闭IsCustomFollowMode，并在另一请求把Yaw/Pitch/Roll SmoothTrack Enabled全部置1；Custom分支启用现有自定义轴设置；3D Roll 360另经轴模式设置。它们不是一个已确认的PF/PTF/FPV单字节枚举。多个请求不声称原子事务，也未审计完整中止/失败补偿。

updateTrackModeShow还在新型号且UserProfile不为2时禁用模式下拉框；table_choice的含义、允许配置与实际固件/物理模式关系仍需核对。该条件不是SDK自动切换table_choice或自行激活预设的授权依据。

## 状态偏移的边界

DataGimbalGetPushUserParams.getPresetID的业务get参数为offset2/width1，isCustomAdvancedSettingProfile据此检查CUSTOM_1或CUSTOM_2。该类继承DJICameraDataBase，不能忽略包层上下文就把业务偏移2直接当作原始BLE载荷偏移。订阅、真实推送格式、型号通知和table_choice与此值的关联还未验收；不据此修改当前反馈解码或activePresetVerified标志。

## 复现

工具ronin_profiles_trace.py固定APK与SDK/UI恢复视图SHA256，输出40个方法指纹、参数记录、两套枚举、条件链及资源列表。证据位于protocol/research/ronin-profiles-evidence.json。APK、派生DEX和完整反汇编继续留在忽略目录，不执行或提交。

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_profiles_trace.py --apk work/research/dji-ronin-2.2.2.apk --sdk work/research/code-banks/business-05-code-restored.dex --ui work/research/code-banks/business-03-code-restored.dex --output work/research/profiles-reproduced.json
```

四个新增边界测试覆盖错误APK、业务偏移/宽度、错误寄存器和控制流前缀。仍须审计完整模式前置条件、其他字段、请求/推送与取消语义，再封装SDK并进行实机验收；全部命令与高级新增门槛保持false。


后续[订阅与包层审计](SUBSCRIPTIONS.md)已在未加密请求型04:24范围追通payload偏移2/width1。ACK偏移和table_choice订阅不得混用；本机推送/活动预设仍未验证，0.7.12已接入显式源布局的被动字段，但本机布局和活动预设仍未验证。


## HG724新模式实际参数与调用顺序审计（运行时仍0.7.16/0.3.16）

ronin_profiles_trace.py现40方法。新列表index2在UI入口清除IsCustomFollowMode后调用GimbalAxisMode ThreeDRoll360，直接跳过setTrackModeHG711；不能直接把index2传该内部函数。SDK继承轴模式setter用FLOWER_SPECIAL_CMD/index34/size1，枚举value<<3，ThreeAxis/TwoAxis/Roll360/ThreeDRoll360→0/8/16/24。UI实际选择仅ThreeAxis与ThreeDRoll360；与index35电机roll360位64不同，不能互换。

FPV(index0)在必要时请求退出360到轴模式0，关闭index132自定义bit0，随后同一普通参数请求把Yaw/Pitch/Roll SmoothTrack Enabled分别index17/18/19、size1置1。Custom(index1)必要时同样退出360，再开启132 bit0，界面轴选择来自既有custom轴缓存，不自动覆盖三轴。源setIsCustomMode只是UI字段赋值，无BLE请求。模式选择仍受源UserProfile2的UI条件限制，不能自动激活预设。

CacheHelper设置调用没有串联确认，UI回调成功更新延时显示标志、失败日志/Toast；没有后续参数写入或固件补偿。源函数调用顺序不是线上包序/ACK串行证明，多请求不等于原子切换。没有新增模式SDK/发送/高级任务或硬件/厂商执行；真正完成切换、部分失败/取消/恢复与本机生效仍待实现/验收。详见tools/research/PROFILES.md与protocol/research/ronin-profiles-evidence.json。

补查ConfigGimbalModeSetView.setAxisStatus只改变六处ImageView可见性，setClicked仅日志和mIsClicked字段，不触发设备写入；两方法纳入40指纹。不能将进入Custom当作自动重写三轴开关。


| 新UI位置 | 目标标签 | 源请求/本地动作（不保证线上完成顺序） |
|---|---|---|
| 0 | FPV | 缓存轴模式为360时请求ThreeAxis/34值0；清132 bit0；17/18/19同包各置1 |
| 1 | Custom | 必要时退出360；置132 bit0；从缓存更新轴图标，不自动重写轴开关 |
| 2 | 3D Roll 360 | 清132 bit0；请求ThreeDRoll360/34值24；跳过setTrackModeHG711 |

TwoAxis/Roll360对应8/16只确认源枚举与通用setter，不是已找到的HG724新列表入口，也不据此扩展模式SDK。FPV中的三个普通开关同包不代表整次切换原子；先前请求仍可能失败，源UI没有串联ACK或参数补偿。后续可先封装有明确源链的原生字段请求，再处理完整模式事务及部分成功语义，不能把上层“已点击”当作固件到位。
