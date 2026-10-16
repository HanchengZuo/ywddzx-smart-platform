# Flask 渐进式重构：备份归档校验

日期：2026-10-16。保留前三批未提交改动，仅本机实施；不更新版本、不提交或推送 Git、不部署、不重启现有服务。

## 本批范围

已复查工作区、README、第三批说明、备份恢复调用链、相关测试与启动验证方式；适用目录未发现 AGENTS.md。归档校验本身不访问数据库，也不拥有锁或后台任务，因此仅提取三个职责：

1. 从 ZIP 成员中选择数据库备份，优先 database.dump，兼容 database.sql。
2. 读取并校验 manifest.json、判断备份类型、写入实际选中的 database_member。
3. 检查 storage 文件成员解析后的目标路径是否位于配置的 storage 根目录内。

实现位于 `backend/backups/archive_validation.py`。app.py 保留三个同名函数及原签名；清单校验显式注入原数据库成员选择函数，storage 校验显式传入调用时的 STORAGE_ROOT。新模块不导入 app、Flask、数据库或 SDK，不接收 globals/整个命名空间，不创建线程或锁，导入不执行文件操作。

```text
原备份导入接口 / restore_full_backup_archive
  -> app.py 原校验入口
  -> backups/archive_validation.py
  -> 返回清单或抛出原有异常

恢复编排、SQL 工具调用、数据库恢复、storage 清空与写入仍在 app.py
```

相对本批开始时 app.py 净减少 23 行，仅三个既有校验函数体与模块导入变化；其余函数和路由装饰器 AST 不变。前三批模块逐字节不变。未提取或改写 restore_full_backup_archive / restore_storage_from_backup，也未合并恢复写入阶段原有的再次路径检查。

## 兼容行为

| 边界 | 保持的行为 |
| --- | --- |
| 接口与权限 | 原 URL/HTTP 方法/endpoint、认证、操作人、管理权限、响应状态/字段/错误文本和上传限额均不变；其他业务数据范围不变 |
| 校验顺序 | 缺 manifest 先报错；然后选数据库成员；再解码清单并检查类型。不会因重构提前检查 storage、读取数据库内容或改变优先错误 |
| 数据库成员 | 两个根目录成员并存仍优先 dump；清单中填写的 database_member 仍被真实选择结果覆盖；不接受大小写不同或仅存在于子目录的同名成员 |
| 清单 | 保留未知字段及原版本兼容性；不新增 schema/version/字段类型验证；非对象 JSON 仍抛 AttributeError，坏 UTF-8 仍抛 UnicodeDecodeError，不统一改为新的错误 |
| ZIP/JSON | BadZipFile 和 JSONDecodeError 保持原 ValueError 文本与异常因果链；缺文件等 I/O 异常仍原样传播；句柄在成功/失败后都关闭，校验不改写 ZIP |
| 路径 | 继续使用当前主机 os.path.abspath/commonpath 规则；跳过非 storage/ 前缀及以斜杠结尾的目录项；合法规范化路径、重复成员和既有特殊路径的接受行为不变，不新增跨平台反斜杠策略 |
| 恢复顺序 | 保存临时上传 → 校验清单 → 提取临时数据库成员 → storage 预检 → 数据库恢复 → storage 恢复；数据库失败不进入 storage，后者失败不补偿已完成的前一步 |
| 锁和配置 | 原授权连接关闭后才进入恢复任务；任务锁及 finally 释放位置不变；恢复失败不写成功配置，成功后仍先释放锁再更新配置；不新增事务提交、回滚或重试 |

## 验证结果

新增 29 项契约测试先在前三批实现上通过，再进行提取；迁移后补充一个新模块导入边界测试。

| 验证 | 结果与边界 |
| --- | --- |
| 新契约测试 | 19 项归档/路径测试和 10 项恢复调用链/HTTP 测试通过；覆盖真实小 ZIP、旧 SQL 格式、非法清单、路径穿越、重复项、错误优先级、句柄关闭、临时文件清理、授权拒绝、失败后锁释放及配置保持 |
| 全部相关回归 | 122 项通过、0 跳过：110 项备份/COS/导入边界及 12 项既有账号代入/展示会话测试 |
| 数据库事务 | 重新运行三项隔离 PostgreSQL 测试，验证 app.actor_id、授权连接关闭及成功/拒绝/失败路径的未提交探针回滚；本批校验模块不访问数据库 |
| 恢复隔离 | 新调用链测试只在临时目录保存上传并提取伪数据库成员；数据库恢复与 storage 恢复均为替身，SQL 命令、storage 清空等危险原语被显式拦截。单独调用真实 storage 恢复函数时，仅使用非法路径并断言在清空前拒绝，不执行实际恢复 |
| 并发边界 | 原线程争用、慢上传期间拒绝恢复等测试通过；新增 HTTP 测试确认校验/恢复失败后释放锁，且失败不改写成功状态；没有验证或修改跨进程互斥 |
| 新旧差分 | 临时脚本对第三批校验函数与新模块比较 295 组成员/清单/路径输入，返回值及异常类型、文本、直接 cause 类型一致；未解压到业务 storage |
| 导入/路由 | 新进程拦截 builtins.open、建目录、外部连接、线程和子进程后，新模块仍可导入且不加载 app/Flask/数据库/SDK；前后 222 条路由、方法、endpoint、请求钩子、扩展和上传限额快照一致 |
| 启动/静态 | 隔离 Gunicorn 两 worker 沿用 app:app，各 worker 原 hook 仅执行一次；版本接口 200、未登录备份 POST 401。为安全拦截数据库连接并替换后台任务。相关源码 compileall 与差异空白检查通过 |

所有运行在本机现有后端容器的 `/tmp` 独立源码副本中进行，未替换 `/app` 或业务 storage。真实事务测试仅在本机创建一次性 `test_backup_transfer_*` 库，测试后删除该库；未写入业务数据库、执行迁移或恢复。COS 使用既有替身测试，没有真实云端操作或付费 AI 调用。

在隔离源码副本的 backend 目录、具备测试依赖时可运行：

```bash
python -m unittest discover -s tests -p 'test_backup_archive_validation.py'
python -m unittest discover -s tests -p 'test_backup_restore_validation_contract.py'
python -m unittest discover -s tests -p 'test_backup*.py'
python -m unittest discover -s tests -p 'test_cos_backup*.py'
python -m unittest discover -s tests -p 'test_account_impersonation.py'
python -m unittest discover -s tests -p 'test_presentation_session.py'
```

前三条命令用于分别运行新测试或全部备份测试，不要把重复执行算成额外测试数量。真实事务三项需显式提供一次性本机测试库的 BACKUP_TRANSFER_TEST_DSN，且库名必须以 test_backup_transfer_ 开头；未配置时会明确跳过，不应称作完整事务验证。

未运行整个项目测试全集；未验证真实数据库/storage 恢复、真实后台调度、实际大归档、COS 网络或生产服务。本批恢复顺序测试不是数据库恢复正确性或跨资源原子性的证明。

## 存量风险与下一批

本批是行为保持的提取，**不是归档安全加固**。以下既有情况已记录或由测试固定，未静默修复：

- 清单没有完整 schema/version 验证，非对象 JSON 可能经接口返回 500；重复 manifest/member 继续按原 ZIP 行为处理。
- 路径检查是词法 containment，不新增 realpath/符号链接或跨平台路径政策；storage/. 等指向根目录的文件项可通过现有预检，却可能在后续写入阶段失败。
- 没有新增解压总大小、成员数量/压缩比或整个归档的提前 CRC 完整性预检；后续 storage 读取失败可能发生在数据库恢复之后。应单独评估资源限制与兼容策略，不能混入结构重构。
- 前三批记录的多进程任务锁/调度标记不共享、JSON 非原子写入、配置竞争、下载前释放锁、COS 部分删除和数据库/storage 恢复非整体原子等风险保持原样。

下一批可先为 storage 备份排除规则、ZIP 打包及本地归档发布补齐临时文件故障测试，再选择独立文件操作边界；继续保留数据库恢复和调度器。跨进程互斥或校验加固须单独作为功能修复评估与交付。完成本批后停止，等待审阅。
