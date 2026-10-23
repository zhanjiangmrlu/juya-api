# V1.5 验收修复 API 锁定契约

2026-10-24，北京时间。用户已批准方案；本文件供后台、小程序和总协调读取。仅统一 API 仓库实施，前端各自在自己的仓库同步 OpenAPI 并生成类型。

## 整批导入软删除

`DELETE /api/admin/v1/imports/{batch_id}`，JSON：

```json
{"expected_updated_at":"2026-10-17T08:00:00.123456Z"}
```

必须原样传入最近 `ImportBatchView.updated_at`，不能重新格式化、截断微秒或本地换算。成功 200：

```json
{"id":"<batch_id>","deleted":true}
```

- 必须有管理员会话、CSRF 和 `Idempotency-Key`。相同管理员相同键同一请求重放原成功回执；不同内容同键 409 `operation_conflict`。
- `GET /api/admin/v1/operations/{key}` 可恢复删除成功回执。失败事务不会留下成功回执；可修正条件后重试。
- 不存在、非本人、已删除且用新键操作：404 `import_missing`。删除后普通读取、恢复读取、确认、继续上传、解析重试、核对、保存、资料移除、导入发音及按批次查询均不得继续操作。既有操作回执仍保留。
- 批次自确认后变化：409 `import_changed`，消息“批次资料已变化，请刷新后重新确认删除”。`updated_at` 包含接受的编辑和关联任务活动；同刻或迟到写入以至少一微秒推进，作为版本值使用。
- 关联已接受的卡片保存处于 queued/running/retry：409 `import_saving`，消息“批次正在保存卡片，请等待保存完成后再删除”。此保护优先于版本错误。
- 成功后普通批次集合和 `resumable_only=true` 集合均不返回该批次。仅软删除批次，不清理卡片、共享素材、成绩、暂存证据或操作/任务回执。已保存成功或失败终结后可删除。
- 解析进度、最终解析/保存提交与删除共享管理员写锁；上传在加锁后重新读取批次。晚到 Worker 不会复活已删除批次。

## 发布、重新上架与排序

沿用预览、单卡发布、批量发布和目录排序接口。新发布、新内容版本、下线后原版本重新上架均移至用户目录最前，其余卡片相对顺序不变。手动排序继续有效；后续发布只把对应卡片移至最前。已上线相同内容再次发布、幂等重放不会重复置顶。

跨管理员的发布最终提交、上下线/删除和完整目录排序共享 `catalog_revision` 数据库行锁，排序预览失效仍返回 409 `catalog_changed`。现存学习队列快照不重排。

下线会推进草稿 revision，即使 `has_unpublished_changes=false`，仍须用最新 revision 创建新预览。`POST /publication-batches` 201 仅代表受理；必须轮询 `GET /publication-batches/{id}` 或对应 job，成员达到 `succeeded` 才显示发布成功。失败成员显示真实 error_code；不得把 queued/running 当成功。

隔离回归验证下线→新预览→批量受理→真实 Worker 成功→未学用户可见；已学卡从待学列表过滤，但已发布详情仍可复习。云端截图所涉卡当前仍下线的证据不足以说明根因已解决，云端排查由主协调负责。

## 记录和反馈

- `/api/mini/v1/me/learning-records` 在计数和 page/limit 分页前 join 排除 `Card.deleted_at` 非空的卡片。
- `/me/checkins/{day}` 明细及 `/me/checkins` 每日 `card_count` 使用同一过滤。历史 Completion、DailyLearning、Checkin 事实和个人成绩、打卡天数保留；因此统计完成数可能大于当前可显示的记录数。
- 新 `records`/`day` 学习队列排除已删卡；既有快照仍保留索引并实时返回不可用。下线安全摘要保留；缩略图和原图权限不扩大。
- 新配置 `Settings.feedback_safety_enabled=False`，环境变量 `JUYA_FEEDBACK_SAFETY_ENABLED=false`。关闭时跳过用户创建、追加、截图和管理员回复的文字/图片审核调用；鉴权、归属、CSRF、字数、类别、图像解码、图片归属、幂等、版本及状态验证继续执行。
- 设置 `true` 时恢复原审核严格规则，仅最终明确 `allow` 通过；reject 为 422，其余结果或不可用为 503。配置 `JUYA_FEEDBACK_SAFETY_URL`/`JUYA_FEEDBACK_SAFETY_TOKEN` 由环境提供。

## 契约及发布边界

权威快照：`openapi/admin.json`、`openapi/mini.json`；生成器 `scripts/export-openapi.py`。本仓库无前端 TypeScript 快照；对应前端自行复制并执行 `generate:api`。

新增兼容迁移 `0017_import_batch_soft_delete.py`：仅增加 nullable DATETIME(6) `import_batches.deleted_at`，旧列集 INSERT 仍有效，历史行不改变。新管理员 API、Worker/镜像探针、runtime preflight 和初始化门禁要求至少 0017；小程序门禁保持原要求。发布时先迁移，停止/排空旧管理员写进程再替换为新代码，防止旧二进制忽略删除标记。一旦产生软删除数据，不能仅回退旧管理员镜像恢复导入服务；须保留识别删除标记的代码或停用全部导入写入口。隔离迁移降级测试仅验证结构回退，不代表旧代码可正确理解新删除语义。

本轮不推送、部署、上传小程序或清理真实业务数据。验证结果、红绿证据及外部边界在 `docs/verification/v15-acceptance-api.md` 汇总。
