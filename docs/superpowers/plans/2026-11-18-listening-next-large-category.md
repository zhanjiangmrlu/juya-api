# 大分类下一篇请求修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 分类文章数量增加后，获取和打开下一篇均不因队列凭据过长失败

**Architecture:** 新增只读 POST `/api/mini/v1/listening/articles/{article_id}/next`，通过 JSON 正文携带 `queue_token`；新旧接口共用队列校验及查找逻辑。小程序使用 POST，并通过绑定账号、目标文章的一次性内存交接传递页面队列，页面 URL 仅携带文章 ID。兼容旧 GET 接口和旧页面参数

**Tech Stack:** FastAPI、Pydantic、SQLAlchemy、Vue 3、uni-app、pytest、Vitest

**Spec:** 用户要求修复生产 HTTP 414，并避免分类文章增多后再次失败；以下设计由实施者选择

## 设计与约束

- 生产 IELTS B2-C1 分类 322 篇，队列约 17.6KB，下一篇 URL 约 17.7KB；已复现 Nginx 414
- 扩大 Nginx 限制仍受队列增长影响；服务端短凭据需要新增共享存储生命周期；本次选择 POST 正文及内存页面交接，无迁移或新存储依赖
- 保留冻结顺序、实时逐篇验权、用户绑定、有效期、分类边界及已确认完成结果
- POST 只查询，不新增幂等写操作，不重复提交学习完成
- 不限制分类文章数量，不修改真实数据；本次仅本地实现和验收，不部署或上传
- 当前两仓 test 工作区干净，在当前工作区实施；不提交、推送或合并其他改动

## Review Focus

- 超过 8KB 的真实签发凭据通过短 URL 到达接口
- 冻结后排序或免费资格变化不改变冻结顺序，也不越权
- 篡改、跨用户、过期凭据仍被拒绝，末篇不回绕或跨分类
- 页面地址不携带大凭据；内存交接不能跨账号复用，失败后可重试
- 下一篇失败重试不重复保存已确认的学习完成结果

## Task 1: 接口、调用和页面交接

**Files:** API `listening_api.py`、`listening_contracts.py`、`openapi_*docs.py`、`tests/test_listening_next.py`；小程序 `listening-service.ts`、`use-listening-article.ts`、`shared/types/listening.ts` 及对应单测

- [x] 先新增真实大分类 POST、旧 GET 与新 POST 权限/顺序/末篇一致性测试，以及前端大队列完成、重试和页面交接测试；运行确认预期失败
- [x] 新增 `NextArticleInput(queue_token: str | None = None)`，GET/POST 共用查询实现；小程序以 POST JSON 查询下一篇
- [x] 页面跳转移除凭据参数，增加绑定账号及目标文章的一次性内存交接，保留旧参数读取；导航失败清理交接
- [x] 运行聚焦测试，确认通过

## Task 2: 契约与验收

**Files:** 双仓 OpenAPI/生成类型，双仓 HANDOFF，API progress，验证记录

- [x] 导出接口，按仓库原命令同步小程序契约及生成类型
- [x] 运行双仓完整测试、静态检查和无上传微信构建；记录环境专属跳过及未验边界
- [x] 审查最终差异，记录结果和发布依赖：先 API 后小程序；旧包仍使用旧 GET，修复需新版小程序生效
