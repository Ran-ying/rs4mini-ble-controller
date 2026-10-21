# Python SDK 0.7.39

Python 3.8+，基于 Bleak 与 asyncio。新部署建议 Python 3.12，当前实机平台为 macOS。运行 Terminal / IDE 需获得系统蓝牙权限。

## 部署

从仓库根目录执行：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ./python
.venv/bin/python -m unittest discover -s python/tests -v
```

SDK 未发布到 PyPI；安装本地 `./python` 目录，Bleak 由 pip 安装。单元测试使用假设备，不连接硬件。在其他项目也可执行 `你的虚拟环境/bin/python -m pip install /绝对路径/rs4mini-ble-controller/python`。

## 连接并读取

保存为仓库根目录的 `read.py`，执行 `.venv/bin/python read.py`：

```python
import asyncio
from rs4mini_sdk import RS4Mini

async def main():
    gimbal = RS4Mini(ioTimeoutMs=3000)
    gimbal.onError = lambda error: print(error.code, str(error))
    try:
        await gimbal.connect(timeoutMs=30000)
        print("姿态角：", await gimbal.getAttitude(fresh=True))
        print("机械关节角：", await gimbal.getJointAngles(fresh=True))

        gimbal.appCommands.useProfile("ronin-2.2.2")
        print("跟随灵敏度：", await gimbal.appCommands.getFollowSensitivity())
        print("电机参数：", await gimbal.appCommands.getMotorTuning(timeoutMs=15000))
    finally:
        await gimbal.close()

if __name__ == "__main__":
    asyncio.run(main())

```

示例读取反馈和参数，不启动运动或校准。电机 12 项逐项读取，多项返回 `readMode='sequential'`、`atomic=False`、`values`、`replies`；不是原子快照。`appCommands` 与 `app_commands` 是同一实例的参数入口，共用已有蓝牙连接。

## 运动调用

稳定器解锁、平衡且周围无遮挡后使用。以下片段替换读取示例 `try` 内的读取部分：

```python
        await gimbal.moveFor(pan=0.05, durationMs=300)
        start = await gimbal.getJointAngles(fresh=True)
        target = (start["yaw"] + 3 + 180) % 360 - 180
        await gimbal.moveTo(pan=target, toleranceDeg=1)
        await gimbal.moveTo(pan=start["yaw"], toleranceDeg=1)
```

`setVelocity(pan=..., tilt=..., roll=...)` 为持续发送的 -1..1 归一化输入，用 `stop()` 结束。`moveTo()` 为主机反馈闭环，Pan=关节Yaw、Tilt=关节Pitch、Roll=关节Roll，单位度；反馈约 1 Hz，默认容差 1°。`recenter()` 为设备三轴回中。

## 参数与命名

| camelCase | snake_case | 说明 |
|---|---|---|
| `getAttitude(fresh=True, timeoutMs=3000)` | `get_attitude(fresh=True, timeout_ms=3000)` | 姿态反馈 |
| `getJointAngles(fresh=True)` | `get_joint_angles(fresh=True)` | 机械关节角字典 |
| `moveTo(pan=10, toleranceDeg=1)` | `move_to(pan=10, tolerance_deg=1)` | 主机定位 |
| `moveFor(durationMs=300, pan=0.05)` | `move_for(0.3, pan=0.05)` | camelCase 毫秒；旧 snake_case 别名为秒 |
| `appCommands.useProfile('ronin-2.2.2')` | `app_commands.use_profile('ronin-2.2.2')` | 显式选择参数来源 |
| `appCommands.getMotorTuning(axis='pitch')` | `app_commands.get_motor_tuning(axis='pitch')` | 读取单轴四项电机参数 |

Python 的 `app_commands` 方法也接受现有 camelCase 选项，例如 `get_motor_tuning(timeoutMs=15000)`；不要假设所有参数都自动转为 snake_case，具体以方法签名为准。`connect(timeoutMs=30000)` 使用毫秒，旧 `connect(timeout=30)` 使用秒，两者不能同时指定。

反馈回调：`gimbal.onTelemetry = lambda sample: print(sample['jointAngles'])`，或 `on_telemetry` 别名；支持同步和异步回调。四类保留设备状态使用 `onAppStatus`，先选择 App 来源。接口返回副本，修改副本不会改变内部缓存。

## 生命周期与错误

`disconnect()` 后实例可重连，`close()` 永久关闭；使用 `try/finally` 释放资源。有限运动和参数写入互斥，冲突抛 `RS4MiniError`，检查其 `code`。`stop()` 取消主机运动，原运动任务会抛 `RS4MINI_MOVE_CANCELLED`；应保存并等待任务，处理该异常。`asyncio` 的外部取消仍传播 `CancelledError`。

自动重连默认关闭，显式启用后也不重放旧运动。参数写入超时不代表未执行，避免盲目重试；BLE 停止不保证中止固件校准。

完整的功能、部署与 Node 对照见[主 README](../README.md)。接口命名可对照 [Node API](../node/API.md)，Python 签名见 [`device.py`](rs4mini_sdk/device.py)、[`controller.py`](rs4mini_sdk/controller.py)、[`app_commands.py`](rs4mini_sdk/app_commands.py)，完整报文与算法见[单文件复刻规范](../docs/SDK_RECONSTRUCTION_SPEC.md)。历史实机与研究记录保留在 `docs/`，不表示已移除接口仍可调用。
