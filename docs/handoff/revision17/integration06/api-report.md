# Task1 后端实施报告

状态：后端实现已提交，当前树完整验证通过；交由controller安排最终评审。未推送。

## 范围与实施

- 0024在0023之上增量迁移。迁移前先完整检查旧免费有效集合和历史topic分类映射，异常收集全部类型/稳定ID后中止，不提前变更schema/data。MySQL用持久snapshot与Alembic autocommit_block保留非事务DDL中断后的原始事实，可重入；不提供会丢直接分类/免费状态的downgrade。
- 旧topic只保留历史映射；文章、草稿/发布归属及候选直接category_id与分类篇序，不生成隐藏topic。分类软删除保留历史FK，对全部未删除文章的草稿/发布引用阻删，共享catalog锁防并发穿透。
- Card/Article独立is_free和free_revision。GET/PUT free-access精确操作一项、持久operate回执、独立版本冲突与稳定对象/管理员/前后状态审计；仅设置变化递增free_revision，内容revision/version不变。下线保留设置，删除不复活/不补位；N/M与旧主题/全局免费排序写返回410。免费汇总是全量只读。
- 统一有效发布&&(is_free||active grant)，正文点词必须active。权限version包含对象free_revision，不依赖可能缺失的旧policy。GET/HEAD/Range旧全文/词音票据交付均重新校验当前权限。
- ListeningPayload增加可选vocabulary，稳定词条ID、英文/本句释义/音标、原句及词项Unicode code point绝对半开范围；多义不合并。未核对来源/正文改动可存草稿，publish校验当前完整原句与词形确认；5表达仍独立必填。词汇不计正文词数与timeline输入。
- 预置词音独立小模块复用现有pronunciation缓存/任务，server按article+version+wordID取词；mini仅can_learn，admin草稿/发布与导入核对试听不写学习事实。引用必须明确单一version/revision；票据重新核对角色/会话/访问/版本/词条。
- 新DOCX模板去主题必填，增加选填四列重点词汇；兼容旧无词和主题标签，分类精确唯一匹配。source_hint保留未核对原句，source=null时纳入待核对候选语义，确认后以权威source为准。导入目标绑定、恢复、草稿/发布双出口、成功不重做/失败重试和未知先查沿用。
- Canonical：空词剔除[]沿用旧v1；有词v2包含有序语义，排随机词条ID/确认状态；原source_hash、成功receipt、候选ID/目标绑定保留；持久category/canonical映射并bump未成功批次revision使旧token过期。只改分类/免费/排序不生成内容version；旧缺省vocabulary与空数组发布比较同义且不改历史payload。
- Mini直接分类分页、分类进度/限制摘要、独立continue、同类next不回绕，末篇给category_id；旧topic GET可读历史映射。
- OpenAPI admin.json/mini.json均由scripts/export-openapi.py新鲜导出，未手改生成契约。精确前端接口见task-1-interfaces.md。

## RED与GREEN证据

所有命令在本隔离worktree执行：`PATH=/Users/lubi/Desktop/juya/.tools/ffmpeg/bin:$PATH PYTHONPATH=src .venv/bin/python ...`。

- `-m pytest tests/test_integration06.py -q` 首次4失败，符合预期：直接category不被接受、旧topic仍可写、缺逐项免费/词汇行为。日志task-1-red.log。
- `-m pytest tests/test_integration06_migration.py -q` 首次2失败：不存在0024字段/预检查行为，日志task-1-migration-red.log。
- 追加草稿来源暂存和contract3预期3失败，日志task-1-additional-red.log；source_hint保留测试预期KeyError，日志task-1-source-hint-red.log；词音互斥引用预期200!=422失败，日志task-1-speech-reference-red.log。
- 最新核心+迁移：16 passed / 3 skipped，task-1-core-green.log。包含legacy空词版本复用、独立免费版本/幂等/下线/删除、词音票据GET/HEAD/Range关闭后403、分类版本复用与删除引用、来源与去重、schema快照中断恢复。
- 最新静态检查：ruff check .通过；ruff format --check .通过（267 files）；mypy src通过（80 files）。日志task-1-ruff.log、task-1-format.log、task-1-mypy.log。
- 完整SQLite上一轮536 passed / 36 skipped（167.87s），task-1-full-final-current.log；该轮启动后追加了词音引用guard及其一项测试，因此最终当前树再次完整执行结果待下方补齐。
- controller串行真实MySQL最终专项21 passed（18.49s）：fresh迁移、历史回迁、0024首次与中断重入、最新13核心行为；证据同目录mysql-final-targeted.log及mysql-validation.log。只用guard确认的本地juya_verify，本agent未读取凭据或自行运行MySQL清理。

## 回归测试适配

旧N/M/主题写测试改为新410行为；共用数据夹具显式创建直接分类和逐项免费/授权，不保留隐藏旧writer。正文词典用明确active授权夹具。历史迁移round-trip限定兼容边界0023；0024单独验证不可逆扩展，保留fresh command.check和0024迁移完整metadata检查。修复fresh MySQL测试依赖全量ORM导入才能清理的缺陷，改专用库反射MetaData清理，可独立运行。

中间完整轮曾出现156、16个失败，分别为旧契约公共夹具与历史测试跨越不可逆0024；已逐项迁移而非skip。MySQL暴露并修复首次snapshot直接bind.commit使最终stamp未提交的问题，改用Alembic原生提交边界并断言首次就是0024。

## 未验边界与交付约束

- 未连接真实云发音/词库/ASR或微信设备；词音票据回归以测试缓存状态和本地合成音频验证，不宣称真实TTS接通。
- 未对业务数据库迁移、清理或写入。正式本地业务升级仍需停双API/worker、备份、核对旧有效集合；旧场景disabled/缺失且存在发布内容、听读free_count=None且存在发布内容会中止待核对。
- 未推送、部署、远程迁移或上传素材。父进程负责最终跨端网络HTTP联调、视觉验收及共享handoff/traceability；本报告不替代这些验证。
- shared docs/handoff/revision17/integration06及docs/superpowers/plans由controller维护，未混入本提交。

## 最终结果

- 最终当前源码完整命令：`PATH=/Users/lubi/Desktop/juya/.tools/ffmpeg/bin:$PATH PYTHONPATH=src .venv/bin/python -m pytest -q --tb=short`。
- **537 passed / 36 skipped，176.36s，0 failed**；日志 `task-1-verified-head.log`。环境跳过包含MySQL和Redis专项，并非无条件通过；真实MySQL结果单列，不与SQLite加总。
- `ruff check .`、`ruff format --check .`、`mypy src`与`git diff --check`通过；OpenAPI新鲜导出无警告。
- 提交：`f5d9ffd6d9cac1284930254f5511475816cbc281` — `feat(listening): 实现整合06分类词汇与逐项免费`。
- 提交范围51文件，包含源码、迁移、测试、两份OpenAPI；父进程待写共享追踪文档未混入。报告及接口清单位于ignored的`.superpowers/sdd/2026-11-01-integration06/`，供本轮交付/评审读取。
- 未解决业务实现缺口：无已知；真实云/真机与跨端网络/视觉的验收边界按上文单列，等待controller最终评审。


## Task1 round1：评审修复

固定基线 `f5d9ffd6d9cac1284930254f5511475816cbc281`；修复提交 **`ca951462d21fb09cd60c7909cf60e9399c412d27`** — `fix(listening): 修复词音锁序迁类篇序和分类缩图`。本轮仅提交7个源码/迁移/测试文件，父进程AGENTS/HANDOFF/追踪资料未混入；未推送。交由controller做固定head scoped复审。

### 已修正的行为

1. 预置词音POST不再在operate前调用会锁批次的reference；callback统一actor → catalog(shared) → batch(FOR UPDATE)，再解析保存词条并请求缓存任务。GET轮询与票据核对使用owned(lock=False)，不取批次写锁；原owned其他写调用默认锁保持不变。持久receipt及当前交付权限重验保持。
2. category-only草稿的draft_category_order只作暂定展示；publish在持有catalog锁时按目标分类现有最大篇序重新分配末位，不复制过期草稿预留值，多个待迁入和期间新建不再碰序。内容version_id不变；next按明确最终序。0024按全部目标主题展平后的实际分类序，再按目标主题序/旧draft_topic_order/稳定ID为待迁入草稿分配唯一尾部展示序，不直接复制旧主题内篇序。
3. 分类缩略图不再读取草稿image_id筛选；遍历发布summary，选择首个非空thumbnail_url。草稿删图、较早文章新增未发布图不会改变小程序分类图。

### RED证据

- `PATH=/Users/lubi/Desktop/juya/.tools/ffmpeg/bin:$PATH PYTHONPATH=src .venv/bin/python -m pytest tests/test_integration06_review.py tests/test_integration06_migration.py::test_draft_category_orders_flatten_all_target_topics_after_existing_articles -q --tb=short`：**5 failed / 1 skipped**，预期失败为最终分类篇序碰撞、两种草稿图泄漏、GET词音实际FOR UPDATE，以及0024待迁入序[2,2]而非[3,4]。日志 `task-1-round1-red.log`。
- controller真实MySQL运行 `tests/test_integration06_mysql.py::test_candidate_speech_and_edit_share_actor_catalog_batch_lock_order`：**1 failed，1.15s**。通过Event安排候选编辑持actor等待词音到actor，旧词音此时已持batch，触发OperationalError/internal_error 500（预期409），日志 `mysql-review-lock-red.log` 和 `mysql-validation.log`。

### GREEN与范围

- `-m pytest tests/test_integration06_review.py tests/test_integration06.py tests/test_integration06_migration.py -q --tb=short`：**21 passed / 4 skipped，6.91s**，日志 `task-1-round1-green.log`。
- 完整当前业务源码 `-m pytest -q --tb=short`：**542 passed / 40 skipped，158.91s，0 failed**，日志 `task-1-round1-full.log`。该SQLite命令不替代真实MySQL专项；MySQL-only测试在此环境按条件跳过。
- controller真实MySQL最终 `tests/test_integration06_mysql.py`：**3 passed，3.41s**，日志 `mysql-review-final.log`，覆盖可控锁序交错、两篇待迁入及新建插入、单管理员两个独立登录会话并发发布连续篇序。
- controller此前修复专项 **14 passed，11.72s**，日志 `mysql-review-fix-green.log`；该选择包括真实MySQL和迁移的SQLite参数，不与完整套件加总。新增0024多主题草稿展平在两数据库参数均通过。
- 中间全marked MySQL有36 passed/1测试准备失败：测试误尝试创建第二管理员，被产品“sole administrator”约束拒绝，未改变产品权限或绕过鉴权。已改为同一管理员双独立会话，最终上述3项文件通过。该用例证明生产actor/catalog锁链和发布顺序，不声称支持或单独证明跨管理员写入；controller可在固定提交后再给统一allmarked结果。
- 新鲜静态检查：`ruff check .`通过；`ruff format --check .`通过（270 files）；`mypy src`通过（80 files）；`git diff --check`通过。日志 `task-1-round1-ruff.log`、`task-1-round1-format.log`、`task-1-round1-mypy.log`。
- DTO/URL/OpenAPI无变化；两个前端无需因此重新生成类型。仅补充draft_category_order是暂定值，发布以最终服务端category_order为准。

未验边界继续为真实云词库/发音/ASR、微信设备和父任务跨端视觉/网络联调；本轮不修改或迁移业务库。

## Controller最终统一MySQL结果

ca95146固定源码：全部mysql marked 37 passed/545 deselected，33.90s；见mysql-verification.json与evidence/mysql-all-final.log。此前21/14/3专项选择有重叠，不相加。最终整体独立审查Approved，无新的Critical或Important。云、设备、业务库升级边界保持。
