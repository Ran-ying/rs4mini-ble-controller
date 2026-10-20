# 仅 SDK 的实机可用性测试

这些入口直接使用设备SDK，不加载GUI或高级运动模块，不进入默认测试/CI。Node/Python导入BleDevice；原生只链接RSBleDevice、RSControlCore、Foundation/CoreBluetooth，运行时确认不存在RSGimbal/moveTo。

测试连接、两帧新反馈、命名读取、degree-info、停止和关闭/断开；默认只读（停止会发送中位帧）。设置本机RS4MINI_DEVICE_ID，不要把设备标识提交到仓库：

```sh
RS4MINI_SDK_TEST=yes RS4MINI_DEVICE_ID='<本机设备标识>' node tools/hardware/sdk-node.mjs
RS4MINI_SDK_TEST=yes RS4MINI_DEVICE_ID='<本机设备标识>' python/.venv/bin/python tools/hardware/sdk-python.py
RS4MINI_SDK_TEST=yes sh tools/hardware/sdk-macos.sh --run
```

macOS入口使用公开connect的系统连接检索/发现策略，没有借用GUI内部对象。`sh tools/hardware/sdk-macos.sh --build`只构建并本地签名，不初始化蓝牙。各入口支持--help。只运行一个控制端。

额外设置RS4MINI_SDK_WRITEBACK=yes才执行灵敏度同值写回：先成功读取0或1，再写入相同值并回读核对。没有切换、运动、回中、校准、平衡、恢复设置、相机或激活请求。此开关不替代人类授权；本次用户已有具体同值写回授权。

输出逐项JSON；任何一项失败均退出1，即使连接等基础功能通过也不把整套测试报告为成功。保留错误码，不用缓存/部分响应冒充查询成功。原生API与其他端的探针数量略有差异，不按总数推断跨端完全一致。采样反映本机当前固件/设置，不是全部功能或跨负载保证。

0.7.36：两个无响应查询已移除；电机探针验证单项1、全量12、按轴4、按参数3的结果与真实响应数量，不接受部分成功。多项有一次总读取期限；结果readMode=sequential、atomic=false，原始单项响应在replies。
