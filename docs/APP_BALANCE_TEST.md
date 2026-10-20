> 已退出公开SDK（0.7.38）：Node复测无实际功能效果后，用户要求移除启动和状态方法。本文只保留历史协议研究，以下示例不适用于当前SDK。水平校准请使用现有sendComponentCalibrationRequest(sourcePart:AUTO)。

# 平衡测试设备接口（0.7.7 / 原生0.3.7）

应用仍使用同一个RS4Mini/RSGimbal入口、连接和队列。显式选择 `ronin-2.2.2` 来源配置，提供启动请求与状态读取；没有实现等待固件动作完成的高级任务。

## 接口

```js
// 仅供明确授权的实机会话；默认测试不执行这些调用。
gimbal.appCommands.useProfile('ronin-2.2.2');
const ack = await gimbal.appCommands.sendBalanceTestRequest({timeoutMs:3000});
const status = await gimbal.appCommands.getBalanceTestStatus({timeoutMs:3000});
```

Python在同一app_commands/appCommands对象提供相同camelCase与 `send_balance_test_request()` / `get_balance_test_status()` 关键字接口。原生RSGimbal继承 `sendBalanceTestRequestWithTimeoutMs:completion:` 和 `getBalanceTestStatusWithTimeoutMs:completion:`。

启动固定写 `04:0F`、载荷 `25 01 40`、flags40，不能传任意值/轴，也没有未经证实的写零中止接口。先停止主机连续运动，独占操作槽到关联ACK、超时或取消。成功返回AppCommandReply及requestedValue64。不会自动重发或修改反馈缓存。ACK仅表示协议响应，不证明固件开始、结束或实际生效。

读取使用 `04:10`、载荷25，按index37/size1上下文解析。保留返回记录第二头字节，不把它当作实际宽度。返回AppParameterReply与balance对象，例如原值9b：

```js
{
  rawValue:155, stateCode:2, state:'FINISH', axisFieldsValid:true,
  axisResults:{
    roll:{rawValue:1,result:'PASS'},
    pitch:{rawValue:2,result:'MARGINAL'},
    yaw:{rawValue:3,result:'FAIL'}
  }
}
```

stateCode为bits6..7：0 DEFAULT、1 TESTING、2 FINISH、3 ERROR。Roll/Pitch/Yaw的结果分别取bits4..5/2..3/0..1；1/2/3对应PASS/MARGINAL/FAIL，0返回null。每轴独立保留rawValue，任一字段为0则axisFieldsValid=false；它只表示字段能否映射，不表示设备结果可信或测试通过。状态非FINISH时也保留原始结果字段，不能当作本次测试的最终结论。即使FINISH也没有程序ID来关联某次请求，physicalCompletionVerified仍false。

## 生命周期与型号边界

timeoutMs默认3000，范围>0..60000。启动响应截止时间从停止前置步骤后开始，停止/I/O沿用已有有界清理。Node/Python查询可与运动共存，原生查询独占并先发中位停止；新接口不保证固件动作期间其他操作可安全并行。

stop/断连/Web失焦会取消尚在等待的主机事务，不保证固件平衡测试中止。启动ACK后操作槽释放，SDK没有继续占用到物理完成，也没有自动发“中止”或回滚；不要把它当作完整固件任务调度。没有新增面板按钮或启动UI。

## 来源与验收

HG724→HG702继承Ronin2.startGimbalBalanceTest，经命名balance_test写64，使用普通0F/10命令空间；不能替换成类名相似的04:40。固定DB.json存在两条同名记录，index37/size1/type0相同、范围0..1和0..255，加载器按名称插入会由后一次成功插入替代前者。SDK仅固定开放源码启动值64，不据范围开放任意写入。

[静态复现说明](../tools/research/BALANCE_TEST.md) 与 [证据](../protocol/research/ronin-balance-evidence.json) 保存14方法指纹、资源顺序与枚举。SDK明确保留零字段为null，避免源码枚举下标减1导致的无效索引被误判为PASS。

本批离线测试覆盖规范向量、全部256原值保留、零/部分结果、命令关联、截断、非零ACK、操作互斥、取消/超时、无重放与无虚构中止。没有扫描、连接、运动、执行厂商代码或实机平衡测试。固件是否接受、负载适用性、真实报告和中止能力仍待受控验收；继承不代表HG724固件/UI启用证明，全部命令和高级开发门槛仍false。
