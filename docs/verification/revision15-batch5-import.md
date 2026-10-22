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

新增 `0016_import_recovery_timestamp.py`，为 `import_batches` 增加非空微秒级 `updated_at`。历史回填取创建、上传及关联parse/save/media任务中的最大已记录时间，不使用迁移执行时间伪造近期活动。旧版没有记录的核对编辑时间无法追溯，这是历史证据边界。

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
