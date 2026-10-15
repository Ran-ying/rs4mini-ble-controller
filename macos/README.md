# RS 4 Mini Control for macOS

使用 Objective-C、AppKit 和 CoreBluetooth 编写的原生控制面板，无需 Node 或 Python。
这是早期速度控制实现，尚未同步 Node 的遥测解码、UUID 缓存和 `moveTo()`。

构建需要 Xcode Command Line Tools：

```sh
sh macos/build.sh
open "macos/RS 4 Mini Control.app"
```

打开稳定器后退出其他蓝牙控制程序，点击“连接稳定器”。方向键控制 Pan/Tilt，
Roll 两键控制横滚；松开停止。“停止”发送中位帧，“回中”执行三轴回中。
UI 驱动力表示虚拟摇杆输入，不能当作已经精确标定的物理角速度。

应用首次运行需要蓝牙权限。`build.sh` 在本地生成并 ad-hoc 签名 `.app`，仓库不分发预编译包。
历史基本速度控制已实测；Node 的位置测试结果不能代替此面板的独立验证。
