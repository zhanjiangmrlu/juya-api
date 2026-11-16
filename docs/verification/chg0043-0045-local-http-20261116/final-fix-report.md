# 最终单波修复报告

2026-11-16。范围为最终审阅的 I1、I2、I3 与相邻 Minor，验收台账对应 T460、T475、T481、T484—T486 的行已更新。

| 仓库 | 完整提交范围 | 变更 |
| --- | --- | --- |
| API | `8f3f25cdb282f8808e177ce507765c55ca7ed812..143fd385b382a51504be90d9cd8e5cb2d6bf0cd4` | 分词词尾 e、共用夹具和听读正式发布测试、验收台账 |
| 后台 | `cea5772bc3b01004d76dbee775683371ecf2842e..7446218001c5da66e162497e21280dfbfeac7bf9` | 历史归类附件展示、取消确认及两类定点回归 |
| 小程序 | `6e618b1234c5247ffac7e3b09ccba868b5726d10..46d9b7e2d64e73aed0a38f3a53e06128fc135e97` | 详情完成、待学列表、本人原回执服务及对应回归 |

各仓均在授权的 detached worktree 中提交；三次 `git status --porcelain` 均无输出，三个范围的 `git diff --check HEAD^ HEAD` 均退出 0。服务端历史建议由 published_note 校验生成，版本指针仍参与快照，未改变接口契约。用 Python 分别解析比较 API 与后台、小程序的 OpenAPI JSON，两个对象完全相等。

## I1 完成冷启动恢复

详情发起完成时持久保存本人原请求，只包含原路径、方法和已看到的正文版本。登录、列表自动显示、切栏及下拉只查询原回执。用户点击“查询并重试原完成操作”先查原键，没有回执才按冻结的原版本和原键写入。点击时至多授权重试一个待确认动作，随后发现的其他动作只查询。成功结果按操作键消费一次，迟到回执不能清掉后来同一卡的另一笔操作。

若旧客户端未保存正文，必须经过主动查询原键得到 404 operation_unknown 后才释放该本地阻塞，页面提示缺少原版本，请重新打开卡片核对状态。不会重构或提交新版正文，也不会把查无回执当作成功。确定的旧版冲突展示后重读列表，网络结果仍未知保留原记录；换号后原账号的记录仍在。

- RED `pnpm exec vitest run tests/unit/features/learning/learning-list.spec.ts tests/unit/sub-packages/scenes/detail-completion.spec.ts -t 'recovers a cold completion|keeps an unknown completion blocked'` 返回 5 failed、2 passed、45 skipped。详情未请求持久化，列表无重发，旧记录仍阻塞。日志 `/tmp/chg-final-i1-red.log`。
- 相邻并发 RED `pnpm exec vitest run tests/unit/services/operation-service.spec.ts -t 'consumes concurrent completion receipts'` 返回 1 failed，迟到的原回执触发第 2 次通知。同键结果只消费一次，并按原键清理记录后修复。日志 `/tmp/chg-final-i1-race-red.log`。
- GREEN `pnpm exec vitest run tests/unit/features/learning/learning-list.spec.ts tests/unit/sub-packages/scenes/detail-completion.spec.ts tests/unit/services/operation-service.spec.ts` 返回 3 文件、72 项通过。涵盖确已提交丢响应、未送达、旧格式、改版、重试再次断网、自动切栏、切号及并发。日志 `/tmp/chg-final-i1-green.log`。
- 独立跨进程验证使用 `node /tmp/chg-final-cold.cjs write <scenario> <disk-file>`，写进程退出后另起 `node /tmp/chg-final-cold.cjs cold <scenario> <disk-file>`。六组不同 PID 从 JSON 磁盘读取实际源码运行生成的记录，全部断言通过。已提交只 GET 并确认一次；未送达两次 GET 后原键 POST；旧格式仅两次 GET，确认次数为零；改版只 POST 原版本并保留零次成功；切号不发 POST；再断网保留 pending。脚本及日志 `/tmp/chg-final-cold.cjs`、`/tmp/chg-final-cold.log`。
- 定点 H5 `node /tmp/chg-final-h5-cold.cjs`。冻结 H5 本地静态产物、真实 headless Chrome、隔离 HTTP Mock、同一临时持久浏览器资料。第一次在真实详情点击完成，POST 断网后退出整个浏览器。重新启动直达空缓存待学列表，进入图解、切精读后点恢复。同一原键和原 v1 断言通过，序列为 initial POST aborted、GET receipt、GET receipt、GET receipt、explicit POST original key/v1、GET list intensive。提示消失且显示全学完。脚本及日志 `/tmp/chg-final-h5-cold.cjs`、`/tmp/chg-final-h5-cold.log`。

## I2 与 Minor 历史附件及确认窗

展示依据取自服务端验证后的 suggestion 与 invalid_pdf 告警。无附件和已有明确移除版都显示“无有效发布PDF”，有效显示“有效发布PDF”，异常只显示对应异常文案。取消、Escape 和关闭按钮在未提交时均释放原选择，未知写入保留冻结操作直至管理员显式重试。

- I2 RED/GREEN `pnpm exec vitest run tests/unit/features/content-catalog/content-workflows.spec.ts -t 'verified attachment'`。修复前 2 failed、2 passed，异常显示“有效发布PDF 当前发布PDF引用异常”，移除仍称有效。修复后四种状态及建议配对全部通过。日志 `/tmp/chg-final-i2-{red,green}.log`。
- Minor RED/GREEN `JUYA_E2E_CHANNEL=chrome pnpm test:e2e tests/e2e/chg0043-0045-catalog.spec.ts -g 'history remains'`。修复前 Escape 后取消勾选再勾选发生 “element is not enabled”；修复后 Escape、X、取消均通过。日志 `/tmp/chg-final-esc-{red,green}.log`。
- `JUYA_E2E_CHANNEL=chrome pnpm test:e2e tests/e2e/chg0043-0045-catalog.spec.ts -g 'history write'` 1 passed。先中断确认写请求，Escape 未丢快照，用户再次确认才重发，两次提交键和正文完全相同。日志 `/tmp/chg-final-admin-unknown.log`。

## I3 可靠分词

仅 dye、singe 在规则分词中保留词尾 e；die 和 sing 保持原规则。共用场景和听读适配夹具增加两对词的正反向，包括正确与错误来源。听读真实应用写 API 先编辑后最终发布，错误来源返回 422，正确 dyeing/singeing 能发布。

- RED `uv run pytest -q tests/test_chg0044_matching.py` 返回 9 failed、119 passed，其中染色对应 dying 的实际发布返回 200，预期 422。日志 `/tmp/chg-final-i3-red.log`。
- GREEN 同命令返回 128 passed，包含 go/do 复合词、hop/hope、普通复数和义项等既有回归。日志 `/tmp/chg-final-i3-green.log`。在扩展多轮发布测试时，第一次 GREEN 运行暴露夹具继续使用发布前修订号而得到 409，随后按发布回执更新修订号，最终运行全绿。

## 冻结版门禁及边界

| 范围 | 命令 | 结果及日志 |
| --- | --- | --- |
| API 静态和打包 | `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv build --out-dir /tmp/chg-final-dist && git diff --check` | 静态全过，382 格式文件、101 类型检查文件，sdist 和 wheel 构建成功。 `/tmp/chg-final-api-check.log` |
| API 完整 SQLite | `uv run pytest -q` | 945 passed、58 环境专属 skipped，293.24 秒。 `/tmp/chg-final-api-full.log` |
| API MySQL/Redis 相关专项 | 私有 env 注入并断言库名后，串行 `uv run pytest -q tests/test_chg0044_matching.py tests/test_chg0043_catalog.py tests/test_study_notes.py` | 独立本机 juya_verify，168 passed，41.87 秒。 `/tmp/chg-final-api-mysql.log` |
| 后台 | `pnpm check && pnpm test && pnpm build && git diff --check` | 67 文件、370 项通过，检查和构建成功。首次静态检查发现 Vue 属性顺序告警，按规则调整后用最终源码完成整套。 `/tmp/chg-final-admin-final.log` |
| 小程序 | `pnpm check && git diff --check`、`pnpm test`、`pnpm build:h5 && pnpm build:mp-weixin:local` | 142 文件、905 项通过；H5 与微信本地包成功，微信包 20 页面及共享音频控制器检查通过。 `/tmp/chg-final-mini-{check,unit,build}.log` |

本轮只写隔离测试夹具，没有写任何真实历史归类、部署、推送或更改账号。客户端 Chrome 故障注入不等于真实微信。最终 SHA 全量真实 MySQL/Redis 由官方 CI，测试部署、目标环境核验与真机验证由后续流程记录。授权、内置查词及动态听读高亮仍暂停。
