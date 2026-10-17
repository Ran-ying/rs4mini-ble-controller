# 固定用户参数推送（0.7.12 / 原生0.3.12）

显式ronin-2.2.2配置下，已有RS4Mini/RSGimbal入口的设备SDK被动解码04:24。Node/Python/Web通过appCommands.userParameterStatus读取缓存，Python另有app_commands.user_parameter_status；原生为appUserParameterStatus。没有发送、主动查询、自动订阅、固件配置或高级任务。

## 消息与布局条件

仅接受sender4→receiver2、commandSet4、commandId24（十六进制）、请求型且未加密消息。ACK/错误端点/其他命令/加密标志不更新缓存。完整已知getter布局至少74字节，短消息不补零也不覆盖旧快照；额外和未知字节均保存在bodyHex。74只是所有已审计字段所需的最小长度，不代表完整固件报文长度或本机布局认证。

| sourceGetter | payload偏移 | 字节宽度 |
|---|---:|---:|
| getPresetID | 2 | 1 |
| getYawSpeed / getPitchSpeed / getRollSpeed | 9 / 13 / 47 | 2 |
| getYawDeadband / getPitchDeadband / getRollDeadband | 17 / 21 / 51 | 2 |
| getYawAccel / getPitchAccel / getRollAccel | 55 / 59 / 63 | 2 |
| getYawSmoothTrack / getPitchSmoothTrack / getRollSmoothTrack | 67 / 70 / 73 | 1 |
| getStickYawSpeed / getStickPitchSpeed | 25 / 29 | 2 |
| getStickYawSmooth / getStickPitchSmooth | 33 / 37 | 2 |

values逐项返回sourceGetter、offset、size、rawValue、rawHex。源码getInt先fillBytes→arrayComb在原字节后追加零高位，再按LITTLE_ENDIAN读整数；因此1/2字节原值为无符号，不夹取65535或把SmoothTrack的非0/1值强行变布尔。参数单位、合理范围及全部未知字节未据名称推断，也不和04:10/32参数索引互换。

preset返回rawValue与源码MovementSettingsProfile名称：0 CUSTOM_1、1 CUSTOM_2、3 FAST、4 MEDIUM、5 SLOW；其他值保留raw，sourceEnum为null。尤其2不解释成M3、PF/PTF或自动激活预设。源模型是通用DataGimbalGetPushUserParams，并非已验证的HG724专属布局。

## 缓存与事件

```js
// 使用已有控制器；只供明确授权的硬件会话，离线测试不会连接。
gimbal.appCommands.useProfile('ronin-2.2.2');
gimbal.onAppStatus = status => {
  if (status.kind === 'userParameters') console.log(status.preset, status.values);
  if (status.kind === 'calibration') console.log(status.state);
};
const snapshot = gimbal.appCommands.userParameterStatus; // null或最近快照
```

onAppStatus现为calibration/userParameters的区分联合，TypeScript调用方按kind收窄。原生复用appStatusHandler，kind相同。查询属性不会等待新帧；timestamp是主机接收时间，旧缓存不是实时确认。通知与getter复制/不可变快照不受外部修改影响，观察者异常沿原有错误隔离处理。

重选协议来源、切换旧研究配置或断开连接会清空缓存。只更新独立用户参数快照，不替换姿态、机械关节或校准状态，不释放或创建运动所有权。deviceVerified、modelLayoutVerified、activePresetVerified与physicalCompletionVerified均false。

## 证据与验收

ronin_user_push_trace.py核对固定APK/bank05的17个getter与getInt/fillBytes/arrayComb，共20方法指纹；拒绝有分支/整数变换/未知宽度的getter前后缀。protocol/research/ronin-user-push-evidence.json记录逐项偏移；统一边界检查逐项对比Node/Python/原生三份目录，Web共享JS。包层依据见tools/research/SUBSCRIPTIONS.md，未执行厂商代码。

本机尚未采到本次布局，需要用户返回后对照固件、App设置和真实04:24样本核对。此功能不会让设备开始推送；没有通知时保持null，不试探订阅或猜测数据。订阅路由/租期/远端停止及全协议仍未验收，全部命令与高级新增门槛保持false。
