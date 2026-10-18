# 参数元数据初始化与订阅频道捕获

固定 Ronin 2.2.2/7096 APK 与六段已恢复代码的静态审计，延续 [订阅目录](SUBSCRIPTION_CATALOG.md)。证据为 `protocol/research/ronin-subscription-init-evidence.json`，13个方法指纹、4处加载器直接调用方法和3个频道字段直接写入构造器。未执行 App、启动厂商线程或接触设备。

## 已确认的源码行为

- 参数管理器静态初始化一个空 HashMap。`setContext` 赋值后调用 `getInstance`；构造器调用 `init`，后者创建 Runnable 线程并 `start`。
- Runnable 读取 `gimbal_param_infos`（res/DB.json）并调用 `readToMemory`。记录逐项写入名称映射；`read(name)` 直接查询该映射。
- BaseCommand 的名称查表构造器只读一次：非空时保存资源 index，空时保留 Java 实例整数默认0。`getId` 直接返回已保存字段，不重新查表。
- 六段可读代码中，BaseCommand.mId 的直接 iput 仅出现在三个构造器。选定加载方法没有 join/await 或方法级 synchronized；这不排除其他代码的外部屏障、反射或全局顺序。
- 检索的加载器调用包括 ServiceManager.init 与 Ronin 基类回调。直接引用目录不等于完整的运行时启动顺序。

因此，21个依赖元数据的键必须区分“对应记录已可读”和“构造时未可读”。逐项发布还允许部分记录可读的静态情形。研究工具的 `captured_channels` 只接受显式可用名称集合；它不模拟线程调度，也不证明真实 App 发生竞争或捕获了0。

## 独立 SDK 的边界

独立 SDK 可以同步采用固定 DB 已加载、HG724 静态条件分支的命名索引表，无需依赖手机 App 的单例或初始化时序。这样选择的索引不能被称为实际 App 当时的捕获值，也不能证明本机路由、通知流或远端取消语义。源码订阅包无 ACK；主机发送完成不等于设备接受。

尚未恢复的第1/7段、反射、其他类加载器和实际调度未被排除。完整命令清单与新增高级功能门槛保持 false。

## 复现

```sh
PYTHONPATH=work/research/analysis-libs work/python312/bin/python tools/research/ronin_subscription_init.py --apk work/research/dji-ronin-2.2.2.apk --bank-dir work/research/code-banks --output work/research/ronin-subscription-init.json
python/.venv/bin/python -m unittest discover -s tools/research -p test_ronin_subscription_init.py -v
```

工具在导入可选解析器前校验 APK 与全部六段哈希。两个独立提取的完整 JSON 已逐字节核对一致；7项测试覆盖缺失/完整/部分元数据、捕获值不随集合更新、非法输入、全部银行哈希预检和证据边界。
