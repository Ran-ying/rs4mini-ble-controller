# HG724序列号GET入口与通用激活模块门槛

2026-10-19；运行时保持0.7.32/原生0.3.32。工具[ronin_activation_entry.py](ronin_activation_entry.py)，证据[ronin-activation-entry-evidence.json](../../protocol/research/ronin-activation-entry-evidence.json)。固定17方法、八段全部直接模块字段引用扫描，不执行反射/厂商代码、不进行查询或激活。

## HG724继承的是CENTER/id7查询

HG724→HG702→Ronin2，最近的getSerialNumber精确签名声明在DJIGimbalRonin2Abstraction，带真实Getter注解`GimbalSerialNumber`。既有[键目录审计](../../protocol/research/ronin-key-support-evidence.json)的同名字面键为无include/exclude限制的String条目；这里没有执行Android注册、反射或验证现场设备实例。

该getter取DataCenterActiveStatus单例，显式设receiverType=CENTER、receiverId=7、TYPE.GET，再调用start。CENTER源value5，GIMBAL源value4；打包接收地址是`(7<<5)|5=0xE5`。这是与通用激活库GIMBAL/id0不同的源码路由，不能把此前DataGimbalActiveStatus路径替代本查询。

DataCenterActiveStatus继承通用激活基类，构造默认CENTER/id7；doPack调用基类，start指定APP→实例receiverType/id、COMMON00:32、REQUEST、ACK.YES和业务Encrypt.NO。源超时1000ms/重复3不复制到SDK。最终加密和实际扩展表仍是会话条件，不保证线上明文。

基类初始版本Ver1_1，CENTER单例没有GIMBAL单例那样额外setVersion；所以首次、未被推送修改的源GET体是`11`。这不是GetVer查询`00`，也不是已经读到的本机版本。通用推送仍可改变该单例版本，后续GET体取实际源版本；SDK不能固定默认版本并假称已协商。

## 成功回调不保证新鲜序列号

Ronin2的$8.onSuccess调用DataCenterActiveStatus.getPushSN两次，并将结果传给CallbackUtils.onSuccess。getPushSN内部先getSN：缓存空时赋读取结果；缓存非空、读取非空且不同时替换；读取为空时可能保留旧缓存。

因此已有缓存old加本次空/短/非法读取可能仍返回old，ACK成功不能证明新序列号。离线source_push_sn_choice仅展示源选择规则，不成为SDK缓存策略。没有运行这个回调或从设备读取标识。

[GET格式审计](ACTIVATION_FORMATS.md)中的业务字节、长度/版本完整性仍适用其通用基类的非BATTERY分支；实际CENTER响应布局未硬件验收。若封装只读查询，必须使用CENTER/id7严格请求关联、明确版本/格式和本次完整业务体，不照搬源缓存成功回退、重试或自动激活。

## V13/V14默认模块不是GIMBAL

通用基类构造将module_type_赋字面值8，源字段名DJI_SENDTYPE_AIRDM368也取8，并建立CENTER_BOARD/LEFT_OR_MAIN组件信息。不要把8当HG724类型枚举103、GIMBAL wire4或CENTER wire5。

八段具名视图扫描精确字段引用，找到4个方法：基类构造、handleDeviceInfoRequest、handleActivateVerifyInfo、setUserInfo。module_type_直接写入只有构造这1处。GIMBAL构造仅调用基类，没有覆写；CENTER构造也只另设路由字段。源V13要求senderType等于module_type_；V14还要求报文module_type等于它。因此在该Java默认状态下，GIMBAL4和CENTER5来包都不通过默认8门槛。

这不证明固件不支持V13/V14，也没有排除native/反射/运行期修改；它证明“类存在/结构能解析”不足以把V13/V14称为已建立的GIMBAL或CENTER流程。源自动用户信息回复只有在前置门槛及解析通过后才可达，不能据其方法存在就在SDK中自动回复。

## 审计范围与复现

```sh
PYTHONPATH=work/research/analysis-libs:tools/research work/python312/bin/python tools/research/ronin_activation_entry.py \
  --apk work/research/dji-ronin-2.2.2.apk \
  --bank-dir work/research/prefix-restored-final-b \
  --output work/research/reproduced-activation-entry.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_activation_entry.py -v
```

方法指纹主要位于bank05；八段扫描覆盖直接module_type_/module_cnt_/componentTypeMsg字段读写，没有把反射或native间接访问算作已排除。Getter注解/最近继承声明与实际注册支持、会话路由、设备接受是不同层次。

13项新增测试覆盖全sender/module字节域、双门槛、显式上下文、源码缓存选择及字节/指令偏移、八段哈希和未验证标志。最终固定输入独立提取两次须一致。

本批把00:32只读序列号候选补充为有HG724继承源码路径的app-code-path证据，但request/response SDK仍未封装。激活/绑定、实际设备、动态版本、加密/扩展表与持久化均未完成。清单49项，两门槛false；没有SDK收发/激活/相机/视觉/高级新增或硬件/liveUI/厂商代码执行。此前“无HG724入口”对本条只读继承源码路径已有补充，不自动提升其他通用GIMBAL、V13/V14或写入结论。

入口审计验收（2026-10-19）：最终工具对固定八段真实输入独立提取两次，17方法/4个直接模块字段引用方法证据JSON逐字节一致。新增13项研究测试，Python3.8/3.12研究各513通过；统一Node269/Web27/Python244/native1290核心+285假设备生命周期+3独立SDK及严格类型/分层/签名构建通过，终态0。四端运行时代码与d518ff2相同，0.7.32/0.3.32安装包不变。00:32只有继承只读源码路径提升为app-code-path，未新增SDK收发/激活/高级功能或硬件/liveUI/厂商执行；清单49项和两门槛false不变。
