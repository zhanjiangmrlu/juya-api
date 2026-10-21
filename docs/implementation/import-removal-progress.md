# Import deletion and removal — 2026-10-21

Authority: user-approved in-chat plan “修复导入误判重复及上传资料移除”

- Backend base: 3b177a5; frontend base: c45c081 in /Users/lubi/Desktop/juya/.worktrees/juya-admin
- Ruling: reuse the existing clean frontend test worktree and backend test checkout, following the prior import-work ledger's workspace/shared-rule exception; no main-branch changes or deployment
- Pre-flight: backend removal DTOs feed generated frontend contracts; response snapshots must not overwrite unrelated local edits or revive removed records; duplicate rows need separate removal selection
- Baseline from planning: backend import suites 33 passed; original frontend import subset 14 passed; latest test worktree will be checked before frontend changes
- Task 1: complete — deleted modern/legacy identities, old saved status and save fallback now require a live card; explicitly selected deleted targets still fail. Atomic ZIP/item removal retains cards/media/receipts and protects accepted saves. Initial new regressions failed on duplicate/saved status and missing routes, then related45 passed
- Task 2: complete — ZIP and card single/bulk controls, independent removal selection, frozen retryable confirmation, missing-target recovery and refresh. Removed upload/staging caches are pruned; delayed snapshots cannot revive removals or overwrite newer staged edits. Existing row-expansion test retained
- Task 3: complete — final backend211 passed /9 external-only skips, Ruff check/format and mypy49 modules passed; frontend93 passed and full format/lint/style/type checks plus production build passed; both diffs pass whitespace checks
- MySQL: dedicated juya_verify only. Initial targeted run24 passed /1 pre-existing media case failed because ffmpeg was absent from that subprocess PATH. With the correct runtime PATH, that case and two real concurrent removal-versus-parse/save cases passed3/3; additional51-root removal passed1/1. All28 distinct targeted cases now have passing real-MySQL evidence. No shared business SQL/OSS data was used
- Browser: final actual Chrome6/6 passed against a fresh isolated localhost API/worker/SQL/media directory. Covers original multiple-ZIP, multiple-folder and partial-failure flows; deleted-card reimport creates a different ID; duplicate removal survives reload; accepted ZIP removal during another transfer and bulk ZIP removal leave the remaining upload working; single/bulk card removal preserves other folders and source ZIP. Screenshots inspected. Earlier two baseline failures were traced to old private fixtures missing mandatory English titles; corrected fixture data rather than product validation
- Final review: one independent read-only reviewer reported two P2 issues and no declined-to-judge/deferred items. Fixed both in one pass with RED→GREEN regressions: conflicted/unwanted local edits no longer have to save before discard; ZIP-root selection is no longer incorrectly capped by the50-card limit. Removal waits only for previously transmitted/unknown writes, reads current server revisions, and suspends autosave for the selected discard scope
- Concurrent card-list ordering changes were preserved and committed separately by their owning task; this task did not alter them
- Delivery: changes retained uncommitted in the existing test checkout/worktree; no merge, push or deployment. No schema migration. Temporary verification servers stopped after acceptance; evidence and synthetic fixtures remain outside Git

## Authorized remote submission

The user subsequently requested committing and pushing this fix to both remote test branches. Preserve the frontend's concurrent query-button commit by fast-forwarding its existing test worktree before final checks. Commit scope is import source, regression tests, generated contracts and verification records only. SSH transport was unavailable; the existing HTTPS credentials successfully fetched both exact repositories. This submission does not deploy either environment


## 测试环境部署与云端验收（2026-10-21）

用户随后授权部署测试环境并验证两项问题。已通过原有发布工具完成测试后台和管理API、worker、dispatcher发布：

- 测试后台：https://test-admin.juyayingyu.com
- 前端代码：`b4c4f6d95c89eca37fa3747fad04477d382943af`，发布版本 `20261021T153019-b4c4f6d95c89-99f24b`
- 后端代码：`a5d5979a4990006cf418c8249411ba8800536464`，发布版本 `20261021T152738-a5d5979a4990-47e8ff`
- 使用对应提交的CI Linux镜像，[后端CI通过](https://github.com/zhanjiangmrlu/juya-api/actions/runs/39623741640)。ZIP及镜像身份校验、公网健康检查和发布保留流程均完成；线上HTML及JS哈希与本地测试构建一致
- 管理端三个服务健康，零重启、无OOM；六个受保护的小程序及基础服务容器身份和启动时间保持不变。未执行数据库迁移，结构仍为 `0013`；发布目标仅为test

真实Chrome访问测试域名，使用专用合成ZIP及实际云端存储、解析任务完成以下四个场景：

1. 导入保存→删除卡片→同ZIP重传：创建不同ID的新草稿；再传能正确判重；重复导入项可移除且刷新后仍为空
2. 其他ZIP传输中移除已接收ZIP，再批量移除两包：剩余ZIP继续处理并保存为草稿
3. 一个ZIP含四张卡片：单独移除一张、批量移除两张，刷新后保留一张及原ZIP，并正常保存
4. 更新目标弹窗请求过程中删除目标：显示已删除提示，可按新增草稿处理，保留本地修改并生成不同ID

四个场景均取得通过记录，最终场景无JS异常及HTTP5xx。首次运行两项通过，另两项因5秒登录等待、20轮自动轮询结束后未操作刷新而超时；调整验收等待并按界面提供的“刷新处理结果”操作后，受影响的两项重跑通过。此过程未修改产品逻辑。前端第一次发布恰逢API重启，健康检查拒绝切换并恢复旧版；待API健康后重试发布成功

只读查询测试MySQL确认新旧卡片ID不同、历史行保留、移除关系仍不存在、剩余源ZIP和导入项一致。共7个专用验收批次、5张合成草稿，验收后均已软删除草稿并清理未保存暂存；已保存结果及素材按既定边界保留。未操作其他业务卡片，未发布验收草稿
