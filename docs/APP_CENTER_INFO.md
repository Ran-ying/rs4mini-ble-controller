# CENTER/id7只读激活信息源候选

0.7.33 / macOS0.3.33 build36。根据[HG724继承源码入口](../tools/research/ACTIVATION_ENTRY.md)，新增显式App来源下的`getCenterActivationInfo`。这是读取本次响应的设备SDK接口，没有激活/绑定写入，也不保证设备已合法激活。

```js
const gimbal = new RS4Mini(); // 正常连接流程另行执行
// 以下操作仅在用户明确开展硬件测试时调用。
gimbal.appCommands.useProfile('ronin-2.2.2');
const info = await gimbal.appCommands.getCenterActivationInfo({
  sourceVersion: 'Ver1_1', timeoutMs: 3000,
});
// info.serialNumberRawHex 保留原字节；sourceSerialNumber保留源转换语义。
```

Python入口为`gimbal.app_commands.get_center_activation_info(sourceVersion='Ver1_1', timeoutMs=3000)`，保留camelCase别名。Web共享Node核心及浏览器GATT适配。原生应用经RSGimbal继承调用`getCenterActivationInfo:@{@"sourceVersion":@"Ver1_1"} timeoutMs:3000 completion:...`。

## 显式格式和受控路由

sourceVersion必须是Ver1_0、Ver1_1、Ver1_3、Ver13之一，没有默认值，不接受OTHER。它声明调用方选择的源格式，**不是SDK已查询/协商的本机版本**。源初始Ver1_1只是选择依据之一；不能自动推断当前会话。

| sourceVersion | GET业务体 | 响应业务SN格式 |
|---|---|---|
| Ver1_0 | 01 | 偏移8、固定10字节 |
| Ver1_1 / Ver1_3 | 11 | 长度偏移8、内容9起，0..16字节 |
| Ver13 | 01 | 长度偏移8、内容9起，0..16字节；不是Ver1_3 |

固定APP02→CENTER5/id7（打包E5），COMMON00:32、flags40。共享查询器只为这个明确命令、单字节01/11和显式App来源允许E5目标；原有GIMBAL04端点不放宽，不能以此发送任意目标或激活体。没有GetVer00、自动协商、重试、订阅维护、重连重放、SET/FAIL或V13/V14自动用户信息回复。

会话、序号、命令集、命令号、ACK位、发送者E5与接收者02必须匹配。04:32电机读取虽同命令号50，不能完成00:32请求。密文ACK、缺返回码、非零返回码分别明确失败；成功ACK后仍要求完整本次业务体。旧版至少18字节，新版至少9且覆盖完整声明SN；长度>16拒绝，不以空串/源零填充或旧缓存回退成功。

## 返回字段

profile/statusCode/acknowledged/bodyHex/message与其他App候选一致；保留复制的原始消息。sourceVersion、receiverByte=229和sourceGetRequestByte说明本次请求上下文。

- activeByte/sourceActiveBit/unknownActiveBits：源active字节及bit0；不判定授权/激活有效性。
- dateRaw：year两字节小端、month/day/hour/minute/second原整数；不补时区、不校验日历。
- serialNumberRawHex、serialNumberLength：本次完整SN原始字节和长度。
- sourceSerialNumber：源转换。ASCII字母数字直接成字符，其他按Java signed byte十进制追加，例如2D→45、FF→-1，不保证等同普通ASCII序列号。
- trailingBodyHex：保留未消费尾部，不猜其他字段。
- dateValidityVerified、actualSessionVersionVerified、activationValidityVerified、modelLayoutVerified、deviceVerified、physicalCompletionVerified均false。

结果不存入全局SN/版本/激活状态缓存，不改变姿态、关节或程序状态。NACK/短包不能返回上次成功结果。Node/Python有限读查询可与运动共存，超时/断线清理当前请求；Python任务可取消。原生沿用查询占槽及先停止主机运动的策略，stop/断线/超时清理槽位；成功或失败后下一个普通App查询恢复04目标与04命令集。

## 验证范围

共享十组源向量覆盖四种格式、signed SN、空SN、尾部、短体、超长声明及NACK。Node/Python验证同命令号不同目标/命令集、错误端点/序号/ACK、密文、并发、超时、迟到响应和断线；Web假GATT与无Buffer解析、原生纯协议和假设备生命周期单独验证。测试不创建真实蓝牙管理器或现场连接。

未验证目标设备固件版本、实际路由/响应布局、传输加密/扩展表及设备接受。SDK接口实现不提升为硬件证明。清单49项，全部非相机命令和新增高级开发门槛仍false。

0.7.33验收（2026-10-19）：十组四端共享契约及严格ACK/版本/长度检查，Node277/Web28/Python3.8与3.12各252、原生1562核心+299假设备生命周期+3独立SDK、研究两环境各513通过；统一检查终态0，严格类型/分层/签名构建通过。Node tarball隔离安装277项和类型通过；wheel隔离安装252项、三模块导入来源核对。Node110文件、wheel39模块、原生ZIP3文件与本次源码/签名构建逐字节一致，原生0.3.33/build36未启动。没有硬件/liveUI/厂商执行或npm发布/远端二进制Release；清单49、全命令/高级门槛false。
