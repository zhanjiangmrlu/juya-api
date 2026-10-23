# V1.5 验收后端修复验证

日期：2026-10-24，北京时间。工作区：`github-repos/juya-api`；基线 `e6e0bc5`，分支 `codex/integrated03-revision15`。仅修改此统一 API 仓库；不改旧 API 或两个前端仓库，不推送、部署、上传小程序或清理真实业务数据。

## 范围与实现

| 问题 | 后端交付 |
| --- | --- |
| 1 | 整批导入 DELETE、归属/会话/CSRF/原始 updated_at 版本、持久幂等/回执恢复、进行中保存 409；集合隐藏及所有旧入口拒绝继续；最终解析/保存和迟到上传重验软删除；仅新增 nullable 删除时间，不删除卡片、素材、成绩和回执 |
| 2 | 新发布、新版本和重新上架移至目录最前，保留其余相对顺序及手动排序；相同内容在线重发/重放不移动；跨管理员发布/上下线/删除/排序共享目录锁；旧学习队列快照不变 |
| 3 | 使用隔离持久数据库和真实 run_job 完整覆盖下线且 has_unpublished_changes=false→新预览→批量受理→job succeeded→未学列表可见，已学仍过滤且详情可复习；没有用受理回执冒充成功 |
| 6 | learning-records 在 count、offset、limit 前 join 排除删除卡；日期明细、每日可见 card_count、新 records/day 队列同样过滤；成绩和打卡事实、天数保留；下线摘要及原有缩略图权限保留 |
| 8 | feedback_safety_enabled 默认 false，JUYA_FEEDBACK_SAFETY_ENABLED；集中跳过创建、追加、截图和管理员回复审核；开启保持原严格最终 allow；业务及权限校验保持，更新 env example、旧反馈说明和测试预期 |

契约：[API锁定契约](../implementation/v15-acceptance-api-contract.md)，权威管理/小程序 OpenAPI 均与实际工厂生成结构逐字比对；管理新增 DELETE，同一路径总数仍49，小程序44且快照无差异。本仓无 TypeScript 快照，前端各自同步并生成类型。

## 先红后绿与重要边界

- 排序回归初始失败于新卡仍按创建顺序；记录回归初始失败于 total=3 而预期2；反馈初始失败于配置字段/开关缺失，随后默认关闭和开启路径均通过。
- 导入删除首轮8项失败：DELETE 405、已准备保存 Worker 没有复查删除；兼容迁移先失败于缺失 deleted_at 列。实现后这些场景通过。
- 同一时钟 tick 核对修改后原删除版本仍成功（实际200，预期409）的回归先失败，再通过单调版本推进修复；新增同刻任务进度及迟到上传提交检查。原恢复测试改为允许最大记录时间之后的微秒版本推进。
- 新管理员门禁4项先失败于0016仍被接受，更新至0017后通过。
- MySQL 管理操作 Worker 在检查冻结快照时，其他事务仍可取得目录锁：确定性 NOWAIT 回归先失败；将目录锁移至快照校验之前后通过。
- 作者自查发现导入发音入口预检后等待管理员锁期间，批次删除仍可能留下发音任务；确定性迟到请求回归先失败于“没有抛出 import_missing”，随后在持锁执行内重读批次和条目版本，专项17通过、1 MySQL条件跳过。
- 完整 SQLite 首轮364通过、2失败、23跳过。失败为旧“已删卡仍在学习记录”的预期，以及旧租约测试只提供任务ID、不携带 owner_id。前者按批准新行为改为记录为空且历史成绩保留；后者改为从持久任务身份取得管理员锁并继续拒绝旧租约。失败日志保留为 `.private/v15-acceptance/sqlite-full.log`。

Ruling：批次 updated_at 同时承担展示活动时间与删除版本，两个接受事件同刻或请求延迟时至少推进一微秒，避免旧确认误删；代价是该值可能比实际时钟略大，应作为不透明版本原样传回，不能前端重格式化。

Ruling：为原子保护批次版本，管理员任务 claim/progress/finish/fail 与 HTTP 写入统一管理员→任务→资料锁顺序；进度、失败和任务完成持久推进批次版本。原“job→file且不写批次”的并发测试据此改为验证等待管理员锁且无锁环。代价是同一管理员的这些短事务互相串行；解码、读取ZIP等耗时工作仍在事务外。

Ruling：保留既有已删除卡的安全摘要缩略图授权规则，不因记录列表隐藏而扩大任何图片/原图权限；记录/每日统计与历史成绩使用不同用途口径，已在契约说明。

## 验证环境与命令

所有 SQLite 测试显式清除 `JUYA_TEST_DATABASE_URL`/`JUYA_TEST_REDIS_URL`，使用 pytest 临时数据库、媒体和合成账号。PATH 加 `/Users/lubi/Desktop/juya/.tools/ffmpeg/bin`，Python 为本仓 `.venv/bin/python`。

```sh
env -u JUYA_TEST_DATABASE_URL -u JUYA_TEST_REDIS_URL \
  PATH=/Users/lubi/Desktop/juya/.tools/ffmpeg/bin:$PATH \
  .venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src
.venv/bin/python scripts/export-openapi.py
git diff --check
```

MySQL 使用已存在专用本机8.4.13实例，127.0.0.1:18216、私有 datadir、`juya_verify`；凭证仅从已有0600私有文件读取，运行前校验 server_uuid、datadir、bind、端口、数据库、当前账户和仅此库授权。Redis 为既有独立127.0.0.1:18215。未重置任何业务库。仓库忽略目录中保存了已有守卫 runner 的本任务副本，仅改变测试选择与日志输出位置，不泄露凭证。

```sh
.venv/bin/python .private/v15-acceptance/run_mysql.py -- \
  tests/test_v15_mysql_concurrency.py \
  tests/test_import_recovery.py::test_mysql_progress_and_zip_removal_do_not_invert_file_and_batch_locks
.venv/bin/python .private/v15-acceptance/run_mysql.py --full
```

专项实际 MySQL 并发8通过（6.78秒），覆盖其他管理员四类目录写入等待全局锁、冻结快照校验所在锁内、保存/删除一方获胜、同键并发只产生一份删除审计，以及进度/移除无锁环。此前包含整批删除/新旧迁移的专项14项已通过，最初4个目录并发测试由于离线初始化仅支持单管理员而未建立第二测试身份；改为测试直接创建合成第二身份后6项通过，不将该测试夹具错误计为产品红绿。

首轮完整 MySQL 为388通过、1失败、3跳过（165.34秒）。唯一失败 `test_mysql_historical_import_upgrade_and_old_image_insert_survive_round_trip` 停在0016后使用当前包含deleted_at的模型，错误为缺列；对齐到head，保留既有历史事实/微秒/旧INSERT断言，两项新旧迁移测试（含SQLite参数）3通过。完整失败日志和证据保留在 `.private/v15-acceptance/full-before-migration-test-alignment.log` 及同名 evidence JSON。此后完成迟到发音边界修复并重新执行两种数据库全套。

最终 SQLite 完整套件：**369通过、24项按环境跳过，71.34秒，退出码0**。MySQL/Redis项目在下述真实环境全套覆盖；SQLite专属并发在此轮实际执行。

Ruff检查通过、184文件格式正确、mypy检查62源码通过、git diff --check通过。两角色工厂OpenAPI与保存快照一致，已运行导出脚本；小程序JSON无差异。

最终 MySQL＋真实 Redis/Celery 完整套件：**390通过、3项SQLite专属跳过，157.45秒，退出码0**；2026-10-24 00:15—00:18，北京时间。包含新旧历史迁移、旧列集INSERT、迁移往返及模型check、整批删除/晚到提交/持久幂等、全部并发和真实队列测试。3项SQLite专属用例已在前述SQLite全套实际通过，两种数据库共393个相同收集用例。

最终成功日志与执行环境证据在仓库忽略目录 `.private/v15-acceptance/full.log`、`full-evidence.json`、`mysql-final-console.log`，SQLite为 `sqlite-complete.log`。未覆盖首轮失败证据。最终修改后再次确认Ruff、184文件格式、mypy62源码、diff及两角色实际工厂/快照比对通过。

## 审查与外部边界

按批准范围逐项自查迁移兼容、锁顺序、幂等先于可变状态、迟到提交、列表过滤先于分页、缩略图最小授权、反馈开关统一入口及实际工厂契约。作者自查发现的迟到发音问题已红绿修复；无保留的本范围P1/P2或延期小项。主协调已另行报告跨仓审查未发现API具体P1/P2，并将在最终本地提交后重启隔离栈重新联调；此处不把作者自查称为独立审查。

第3条云端只读证据由主协调提供：截图卡当前仍 offline，最近可见成功发布早于截图后的修改，目标账号未完成该卡。该证据排除该账号已学过滤作为现状原因，但不足以确定用户操作为什么未最终发布。隔离回归通过不代表云端故障已解决；未登录云端、改卡或运行云端任务。

0017 保留旧 INSERT 形状，但旧二进制不理解删除标记；实际上线需先迁移、排空旧管理员写进程再替换代码。出现软删除后不能仅回退旧镜像恢复导入服务，须保留识别软删除的代码或停用全部导入写入口；结构降级测试不代表旧代码业务回退保证。此轮未迁移、重启或部署任何现有业务运行环境；真实微信、云端业务、OSS及启用审核后的真实内容网关接入均待外部验收。
