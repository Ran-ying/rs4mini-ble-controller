# Web Bluetooth 0.7.6

从仓库根目录启动本机服务：

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

打开 `http://127.0.0.1:8000/web/`，使用提供 Web Bluetooth 的浏览器。设备选择必须由点击触发。页面会导入 `../node/src/controller.js`、协议和遥测模块；不能只发布 `web/` 文件夹。

`RS4Mini` 提供与 Node 一致的 `connect/setVelocity/setVelocityDeg/moveFor/getAttitude/getJointAngles/moveTo/stop/recenter/disconnect/close`。连接参数、位置参数、错误码和并发规则见 [Node API](../node/API.md)。`device` 保留原生 BluetoothDevice；当前实例可重复连接已选择设备，跨页面持久化授权依浏览器实现，本 SDK 不承诺。

浏览器返回字节为 Uint8Array；Node 返回 Buffer。为兼容旧 Web 调用，`velocityFrame(sequence, pan, tilt, roll)` 仍可使用，也支持 Node 风格的对象参数。

页面显示姿态与机械关节，首次反馈将目标输入填为当前角度；勾选要移动的轴后低速定位。未选轴不运动，已进入 1° 容差的轴归零。页面隐藏、失焦或离开时请求停止；浏览器挂起、关闭或断线可能阻止停止帧送达，必须有人现场观察硬件。

```sh
npm test
```

测试模拟原生 GATT 事件、设备选择、通知、位置闭环、断线和失焦；并在无 Node Buffer 的进程中检查共享模块。测试不打开真实设备选择器、不连接蓝牙。浏览器/系统权限与新运动行为仍待 [统一实机验证](../docs/HARDWARE_CHECKLIST.md)。
## 0.7.2 非相机扩展

Web SDK 随共享核心增加 `enableAutoReconnect()`、`disableAutoReconnect()`、
`runTrajectory()`、`moveThrough()`、`captureHome()`、`moveHome()`、`getOrientation()`。
语义与参数见 `../node/API.md`。自动重试只使用本实例已选择的设备，不从后台弹出选择器；
浏览器权限撤销或关闭页面后，需要再次点击连接。网页失焦也会取消新增轨迹。
页面已加入自动重连开关、保存位置与按勾选轴返回、JSON 轨迹/路点载入和执行、显式四元数转换及实验 JSON 入口。
载入文件不会自动执行；“用当前角度生成路点”可生成本机真实起点再编辑。
`../examples/motions/` 提供共用格式，实验命令只允许已列明的几种类型，不能借此发送任意 DUML。
页面事件已有假 DOM 验证；本机可视布局和真实浏览器权限/硬件效果仍待统一检查。

## 分层与前置条件

本版将设备访问与高级运动分为两个模块。应用继续使用原有 `RS4Mini`（原生为 `RSGimbal`）一个入口，
基础操作也通过它访问设备 SDK；不新建第二条连接。底层命令尚未全部解析/验收，在此之前不新增高级功能。
模块映射和限制见 [架构边界](../docs/ARCHITECTURE.md)，命令证据见 [设备命令审计](../docs/SDK_COMMANDS.md)。


当前 App 来源参数 SDK 提供显式配置下的参数读取和跟随灵敏度读写，复用既有连接。调用入口、各端差异与未验收边界见 [参数 SDK](../docs/APP_COMMANDS.md)。全部底层命令仍未完成，高级功能开发继续暂停。


0.7.4 新增显式当前App来源的自定义跟随与电机设置位字段读取/修改；保留其他位、共享事务截止时间和操作槽。入口及未验收边界见 [命名设置SDK](../docs/APP_SETTINGS.md)。


0.7.5 封装当前型号路径的无ACK自动调参请求、校准状态查询/通知，严格区分本机写入、设备报告与物理完成。接口和待验收边界见 [调参请求与状态](../docs/APP_CALIBRATION.md)。


0.7.6新增十二个命名电机数值参数的31/32读写，和普通用户参数命令空间分开；源码范围与实际设备效果分别验收。见 [电机参数SDK](../docs/APP_MOTOR_TUNING.md)。


0.7.7（原生0.3.7）新增平衡测试启动请求和状态/三轴结果读取，应用统一入口和显式当前App配置不变。接口、端差异和固件停止/完成未验收边界见 [APP_BALANCE_TEST.md](../docs/APP_BALANCE_TEST.md)。


0.7.8（原生0.3.8）新增sendAutoCalibrationRequest/getAutoCalibrationStatus及各端等价接口，与6A/6E自动调参分开。完整API、端差异和未验收边界见 [APP_SYSTEM_CALIBRATION.md](../docs/APP_SYSTEM_CALIBRATION.md)。


0.7.9（原生0.3.9）新增get/setFollowSettings与get/setRcSettings及各端等价接口：六组参数按轴custom/low/middle/high档位，先读后改写，保留其他轴和低两位。接口与未验收边界见 [APP_FOLLOW_MODES.md](../docs/APP_FOLLOW_MODES.md)。
