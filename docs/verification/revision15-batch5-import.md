# 修订15批5：真实可恢复导入集合

日期：2026-10-22（北京时间）  
范围：CHG-0022、需求17.6、T192—T197；基线提交 `a1f74aa`

## 行为与契约

- `GET /api/admin/v1/imports?resumable_only=true` 返回当前管理员全部真实可恢复批次，按最近实际更新时间排序，不受历史查询的5条限制影响；普通历史查询保留原行为
- 批次新增 `resumable`、`stage: upload|processing|review|result`、`source_names`、`updated_at`；来源只返回文件名称，不泄露存储位置
- 显式恢复使用 `GET /imports/{id}?require_resumable=true`，重新检查归属、阶段和实际暂存；失效、他人批次或已完成返回 `409 import_not_resumable`。普通当前批次读取仍允许查看完成结果
- 排除空批、本地未传输入、全saved/duplicate、全不可读且无法重试、原始输入缺失且没有核对暂存的批次。可编辑核对JSON、适用失败项、持久源上的处理中任务以及保存中/混合结果可恢复
- 可用的独立图片/音频尚无DOCX时恢复到上传；保存任务及任何已有保存结果恢复到结果；其他按真实解析与核对状态派生。失败不自动重试，导入仍只保存草稿
- 无效源（含损坏ZIP、音频格式与后缀不符）要求修正重传；适用重试还需确认源对象存在。存储服务查询失败返回503，不能冒充零批次

## 持久时间与迁移

新增 `0016_import_recovery_timestamp.py`，为 `import_batches` 增加可空微秒级 `updated_at`，兼容先扩展数据库时仍在运行及应用回滚后的旧管理镜像INSERT；新代码写入真实时间，旧写入缺省值由新读取回退到已有创建／文件／任务事实，不提供伪造近期活动的服务器默认值。历史回填取创建、上传及关联parse/save/media任务中的最大已记录时间，不使用迁移执行时间伪造近期活动。旧版没有记录的核对编辑时间无法追溯，这是历史证据边界。

创建、上传、暂存、素材匹配、重试、移除和Worker应用结果记录实际变更；读取还合并关联任务时间。解析进度沿用现有job→file锁路径，只更新该已锁Job的真实时间，避免引入batch行锁与移除形成循环。上传在管理员锁内刷新预检缓存的批次时间，旧请求不覆盖较新的编辑时间。普通读取不刷新时间。

部署门禁：管理API、管理Worker、preflight及管理员初始化需schema≥16；小程序API仍≥15，小程序Worker/preflight仍≥10。后续只允许按既有显式迁移流程先升级schema，再启用新管理代码；本任务没有执行部署。

## 自动验证

所有测试均在本工作区，清除 `JUYA_TEST_DATABASE_URL`、`JUYA_TEST_REDIS_URL`，使用临时SQLite及合成素材。Python工具来自已提供的主仓虚拟环境，`PYTHONPATH` 指向本工作区；ffmpeg来自本地工具目录。

```sh
env -u JUYA_TEST_DATABASE_URL -u JUYA_TEST_REDIS_URL \
  PATH=/Users/lubi/Desktop/juya/.tools/ffmpeg/bin:/Users/lubi/Desktop/juya/.tools/node/bin:$PATH \
  PYTHONPATH=$PWD/src /Users/lubi/Desktop/juya/github-repos/juya-api/.venv/bin/pytest -q
```

- 最终全套：**306 passed，13 skipped**。跳过12项真实MySQL门禁及1项真实Redis门禁；没有连接总协调独占实例或其他业务库
- 新增恢复回归：空、一、多及超过5条、所有权、实际源缺失、真实Worker读源前/读源后丢失源、持久核对、阶段与时间、完成/重复排除、混合结果仅重试失败且不重复草稿、存储查询失败、无效ZIP与音频源、进度时间、旧上传预检时间回退
- 新增真实MySQL进度/ZIP移除交错门禁：在file锁与batch锁都已持有时继续进度，检查无死锁且已移除源不重建；本工作区按授权跳过，须由总协调在独占实例串行复验
- 迁移与部署专项：**20 passed**，包括SQLite新建、0015增量、回退再升级、微秒时间最大值回填、原业务行完整保留、外键检查、Alembic模型一致性、管理/小程序分角色门禁和无连接MySQL离线DDL
- `ruff check .`、`ruff format --check .`（163文件）、`mypy src`（59源码文件）、`git diff --check` 全部通过
- 重新导出角色OpenAPI，只有管理契约发生变化；管理端同步其JSON与生成类型

## 审查与联调边界

独立只读审查发现并修复进度锁序和上传旧缓存更新时间回退，补充回归后复审无剩余发现。MySQL锁门禁的交错时钟也经复审修正，不能将SQLite检查称为MySQL并发通过。

管理端采用本API分支启动独立 `127.0.0.1:18325` HTTP服务和新建临时SQLite，管理H5使用4195。合成账号、源文档和所有草稿只存在该临时目录；零/一/超过5条选择、核对暂存、混合结果适用重试等浏览器证据见管理端同名验证文档。没有使用主协调的API/H5/MySQL/Redis端口。

真实MySQL/Redis、OSS远端对象探测、真实云服务及生产部署均未在本任务验收。无推送、部署、体验版上传或已有业务数据清理。

## 集成前独立审查与最小修复（2026-10-23）

总协调将批5择取至主API后，独立审查另实证两项P2，并授权在主API修复。隔离原批5工作区未修改，以下仅使用临时SQLite；未连接18216／18215，未重跑完整套件。

- 旧写兼容：原0016将新列收紧为NOT NULL，旧镜像省略该列INSERT失败。新增真实0015→0016迁移后旧列集INSERT回归先RED（IntegrityError），再改迁移及模型保留nullable；新API实际HTTP读取回退原创建时刻，上传后写入真实更新时间。保留历史最大值回填、回退再升级及Alembic模型check。
- 更新时间倒退：较早stage请求等待保存Worker后解除item.job_id，原批次只保留Worker准备时刻，失去已呈现的较晚完成时刻；删除最后来源或替换失败任务也可能丢失已记录最大值。新增真实路由与Worker受控交错、旧／新接受时钟、移除来源及重试替换共4例，原全部RED，再全部GREEN。此控制序列验证时间语义，不声称SQLite完成MySQL锁并发验收。
- `touch_batch`在API管理员锁内取实际clock，并用普通SELECT聚合现存来源／素材／保存任务时间，另保留即将解除的任务ID。删除ZIP仍先锁批次再删除文件，删除完成后按保留ID再读取可能刚提交的解析进度时刻。无额外Worker批次锁，原进度job→file锁序保持不变。核对、文件／卡片移除、匹配、重试、保存重试、上传均检查其引用及时间保留边界。
- 主API局部验证：`pytest -q tests/test_import_recovery.py tests/test_import_recovery_migrations.py tests/test_imports.py tests/test_import_removal.py tests/test_deployment.py tests/test_feedback_migrations.py tests/test_migrations.py`，**77 passed，4 MySQL门禁 skipped，11.80s**。迁移专项单独4通过。`ruff check .`通过、`ruff format --check .`确认173文件、`mypy src`检查62源码通过，`git diff --check`通过。

随后总协调在隔离真实MySQL与Redis运行完整套件：354通过、5失败、3项SQLite专属跳过，130.13秒。导入恢复、真实并发及在线迁移用例未失败；5项失败均为部署测试的迁移标记表隔离，不能将该次完整运行报告为通过。

独立核对发现`alembic_version`不属于业务Base.metadata，MySQL fixture重建业务表后会保留前序worker probe建立的标记表。新增runtime preflight三个参数与bootstrap两个参数直接CREATE导致1050 already exists。保留原始无秘密失败日志及运行证据为私有`final-before-marker-fix.log`／`final-before-marker-fix-evidence.json`，未覆盖原记录。在临时SQLite预建残留表后分别调用这两个真实测试，先均RED，再仅在两处CREATE前补DROP IF EXISTS，5个参数组合均GREEN；没有修改生产代码。部署专项16通过，Ruff／173文件格式／mypy62源码／diff检查通过。此前7个P2改动复核无新增发现，真实完整套件最终复跑由总协调负责；本次修复未访问共享实例。

此次未提交、推送、部署，也未修改主实施台账。

## 总协调最终真实MySQL验收（2026-10-23）

上述待复验项已在最终主线真实MySQL8.4.13＋Redis完整套件中执行，**359通过／3项SQLite专属跳过，124.19秒**；SQLite专属另跑3通过。包含新增进度／ZIP移除锁序、两项移除并发、完整fresh head及模型检查。5项部署marker隔离失败已最小修复，最终全套无失败。

另补`tests/test_import_recovery_mysql_migration.py`并在同一核对过身份的专用MySQL串行单独执行，**1通过，0.76秒**：6类历史批次微秒回填（含关联parse/save/media及无关任务排除）、旧0015列集INSERT不含新列、nullable与读取真实创建时间回退、downgrade15／upgrade16原行保留及两次Alembic check。没有修改生产代码；首次专项漏填Settings测试密钥造成配置失败，补合成配置后通过，未掩盖为业务红绿。

最终Ruff／175文件格式／mypy62／diff检查通过。所有数据均为私有`juya_verify`库合成事实，未触及已有业务库；OSS远端及真实云安全仍另验。总结果见[最终集成](revision15-final-integration.md)。
