# 扩展代码备份恢复与界面调用方

2026-10-16，运行时保持0.7.8/原生0.3.8。默认ronin_code_restore.py仍恢复business05；新工具ronin_code_banks.py将同一严格方法扩展到固定APK中所有具备结构佐证的段。不运行、安装、修补执行或发布厂商App。

## 恢复范围

固定APK仍为Ronin2.2.2/7096，SHA256与既有证据一致。8段均定位到各自fdex/dgc2备份，按段要求准确文件名；没有因名称相似跨段选取。6段的元数据具有未损坏字符串索引后缀佐证，进一步完成每条原代码备份到encoded_method code_off ULEB槽位的匹配、当前/备份完整长度与指令单元数、异常表边界和目标区域不重叠校验。

| 段 | 备份项名 | 完整恢复code_item数 | 状态 |
|---|---|---:|---|
| 00 | classes.dex.dgc2 | 16,898 | 已恢复 |
| 01 | classes2.dex.dgc2 | — | 元数据缺少相同后缀佐证，未恢复代码槽位 |
| 02 | classes3.dex.dgc2 | 2,689 | 已恢复 |
| 03 | classes4.dex.dgc2 | 6,542 | 已恢复 |
| 04 | classes5.dex.dgc2 | 1,786 | 已恢复 |
| 05 | classes6.dex.dgc2 | 19,436 | 已恢复，与原恢复视图哈希一致 |
| 06 | classes7.dex.dgc2 | 2,191 | 已恢复 |
| 07 | classes8.dex.dgc2 | — | 元数据缺少相同后缀佐证，未恢复代码槽位 |

合计49,542条。未恢复段虽然能读出备份表，不等于已匹配到可靠方法元数据；不推测代码槽位，也不称全App或全协议完成。完整各段摘要与哈希见 [ronin-code-banks-evidence.json](../../protocol/research/ronin-code-banks-evidence.json)。完整备份记录、DEX、APK和反汇编留在忽略目录。

原business05恢复SHA256仍为4fdbd74a05df63d72a0feb1c907d9395426ec3cdb5d6aeb45e3836d856d66654，已有SDK静态证据保持有效。

## 跟随/摇杆字段的下一步

六个设置在SDK抽象层只作为整数字段传递。此前单段恢复没有找到其UI调用方；新恢复的business03中找到40个引用FollowSpeedMode、FollowDeadZoneMode、FollowAcceMode、RcSpeedMode、RcDeadZoneMode或RcSmoothMode的方法。

可选检查只输出类/方法签名、code_offset、指令指纹和引用键，不分发完整方法体。证据见 [ronin-control-mode-callers.json](../../protocol/research/ronin-control-mode-callers.json)。其中fieldSemanticsFullyAudited=false：引用存在不代表位语义、型号分支、单位或SDK已经验收。

初步读到ConfigUserProfileView的设置方法将值分别左移2/4/6后相加，SmoothTrack界面也会按位取值；说明不能把它们当作单一轴数值或PF/PTF/FPV预设。下一步需继续核对各轴位置、枚举、保留位、共享字节的读改写、具体型号UI路径与通知。当前不新增原始字节写接口、发送允许列表或高级功能。

## 复现

标准库恢复：

```sh
python3 tools/research/ronin_code_banks.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --output work/research/code-banks
```

可选Androguard4.1.3调用方指纹检查，同样只解析、不执行：

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_code_banks.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --output work/research/code-banks-inspected --inspect-control-modes
```

工具先校验固定APK哈希；UI检查额外校验固定恢复段哈希。两个独立输出目录实际复现各段摘要一致。标准库测试补充不同段名字隔离、不支持名字拒绝、错误APK/UI视图在可选分析前拒绝，原有长度/异常表/重叠检查继续回归。两种Python环境研究测试各48项通过。

所有输出仅用于离线研究，不能作为可运行APK或设备兼容证据。用户离家期间没有扫描、连接、移动稳定器或启动实时UI；全协议与高级开发门槛保持false。
