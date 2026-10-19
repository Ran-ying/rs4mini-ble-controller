# COMMON00:32 GET、旧推送及V13/V14源格式

2026-10-19，运行时仍0.7.32/原生0.3.32。只读工具[ronin_activation_formats.py](ronin_activation_formats.py)，证据[ronin-activation-formats-evidence.json](../../protocol/research/ronin-activation-formats-evidence.json)固定bank05的34方法。工具校验全部八段输入哈希，但本批方法审计仅bank05，不冒充八段调用扫描。依赖前序[版本审计](ACTIVATION.md)与[包层审计](ACTIVATION_RECEIVE.md)。未执行厂商代码或处理器、未操作硬件，未新增SDK接口。

## GET必须带上下文和版本

源GET请求值按版本为Ver1_0/Ver13/OTHER→1，Ver1_1/Ver1_3→17。它们仍是00:32业务字节，不能当独立命令号，也不能把GET和GetVer查询混用。

GET业务响应字段为active字节0取bit0、year偏移1宽2小端、month/day/hour/minute/second依次3/4/5/6/7。旧版GIMBAL的SN在8起固定10字节；其他版本长度在8，内容从9起，源长度大于16返回空字符串。BATTERY旧版有逆序转换分支，不套到GIMBAL。

离线助手get_status_view要求显式GET上下文及版本名，旧版至少18字节，新版至少9且覆盖完整声明长度。拒绝短体及长度>16，不把源零填充、空串回退或缓存残值当作完整结果。日期数值保持原样，不验证公历/时区；active位不是已验证的激活有效性。

源getRevertSn不是普通ASCII：只有0–9/A–Z/a–z字节直接转字符，其余按Java有符号byte的十进制文本追加；例如00→字符串0，2D→45，FF→-1。源拿aget-byte的符号扩展结果与int255比较，FF不会因此被跳过。离线转换保留此行为，并同时给原始SN字节；不能据名字擅自“修复”成ASCII串。

## 旧推送另有布局和状态副作用

setPushRecData最少11字节；长度比较用v1=11，随后ACK判断将同一寄存器改为1，后续get和SN调用使用覆盖后的1。不能只抓第一个常量就把字段宽度推成11。审计同时检查生产者与中途寄存器改写。

旧PUSH类型3时GIMBAL SN从偏移1取10字节；新版类型19时偏移1的一字节为声明长度，SN从偏移2开始，最多16。与GET的8/9偏移不同。源新版随后把TextUtils.isEmpty(pushSN)的结果直接写进名为isPushActivated的静态字段，没有取反，因此这个字段不能按名字解释为激活成功。

非上述旧类型的业务包还会先把源version设成Ver13再进专用分发；不识别的首字节也可能只改变源版本并发事件，不证明实际协议版本。离线工具没有照搬这种自动版本判定或全局缓存。source_integer_read单独展示DataBase的短体零填充和Integer低4字节行为，它不是GET完整性校验器。

## V13设备信息结构

必须显式选择sourceV13格式；首字节51（0x33），至少23字节：

| 偏移 | 内容 |
|---:|---|
| 1..4 | safe_cmd_type，32位小端Java int |
| 5..20 | 16字节NONCE，保留不解释 |
| 21 | activate_module_count，uint8 |
| 22 | device_num_length，uint8 |
| 23起 | device_num，源复制min(声明长度,剩余字节) |

截断不会自动视作完整，声明长度和实际复制长度分别保留；额外尾部保留。safe_cmd_type为有符号32位，不是另一个DUML命令号。本工具不使用NONCE生成任何响应。

## V14验证信息结构

首字节54（0x36），至少143字节。54是格式标记，**不是DJIActiveVersion的枚举值**；源handleVer13Parse也负责将其转到V14处理。

| 偏移 | 内容 |
|---:|---|
| 1..4 | safe_cmd_type，32位小端Java int |
| 5 / 6..37 | 声明device_num_length / 固定32字节device_num |
| 38 / 39 | module_type / module_no_activate_cnt |
| 40 / 41..72 | 声明board_num_length / 固定32字节board_num |
| 73..104 | 固定32字节time_info，保留不解释时间 |
| 105 / 106..137 | 声明user_id_length / 固定32字节user_id |
| 138 / 139 / 140 | device_type / verify_algorithm_type / verify_code_length |
| 141..142 | reserved_length，uint16小端 |
| 143起 | 源合并reserved+verify，最多复制实际剩余长度 |

三个声明字符串长度不决定后续偏移，固定区总是32字节。声明>32保留并标越界，不顺延布局；尾部保留声明和复制长度，不擅自拆分验证码/保留段。没有验证算法、签名/授权、有效激活或绑定结论。

## 源处理器有发送副作用

handleDeviceInfoRequest在源senderType/module_type_门槛后生成事件并调用setUserInfo；后者生成135字节、首标记53的用户信息请求，取UTC Calendar、序列号和NONCE，向来包senderType/senderId发COMMON00:32请求。源含超时/重复策略，不复制到SDK。

handleActivateVerifyInfo另检查senderType与module_type以及报文module_type是否匹配，再生成验证事件。源运行期module_type_、模块数/先后顺序和HG724用途未验证；解析出这些字段不表示可以执行对应激活流程。

因此本工具完全不调用源处理器，不发事件、不回复用户信息、不联网、不改激活状态，不构造DUML帧。原始结构、长度完整、源枚举与合法激活是不同结论。

## 复现与剩余门槛

```sh
PYTHONPATH=work/research/analysis-libs:tools/research work/python312/bin/python tools/research/ronin_activation_formats.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/prefix-restored-final-b \
  --output work/research/reproduced-activation-formats.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_activation_formats.py -v
```

16项新测试覆盖全字节SN/active/长度域、所有短前缀、uint16尾部长度边界、signed int32、输入快照、寄存器常量覆盖、八段哈希和未验证标志。最终工具固定输入独立提取两次须逐字节一致。

HG724实际入口、接收扩展表与会话、GET关联/版本、设备接受、网络激活与绑定/持久化仍未完成。SDK收发未开放，清单仍49个命令/缺口；inventoryComplete与advancedDevelopment.allowed保持false，无硬件/liveUI/厂商代码执行或高级功能新增。

格式审计验收（2026-10-19）：最终工具对固定真实输入独立提取两次，34方法证据JSON逐字节一致；新增16项研究测试，Python3.8/3.12研究各500通过。统一离线Node269/Web27/Python244/native1290核心+285假设备生命周期+3独立SDK及严格类型/分层/签名构建通过，终态0。四端运行时代码与bcd24ac相同，0.7.32/0.3.32安装包未变，无SDK收发/激活/硬件/liveUI/厂商执行或高级新增，全命令与高级门槛false。
