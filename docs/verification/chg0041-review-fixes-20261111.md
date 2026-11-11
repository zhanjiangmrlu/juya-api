# CHG0041 独立审查修复验收

统一修复范围严格限review-report的R1—R4及测试夹具适配，不推送、部署、上传、修改原配置/数据或原服务。R4由根代理按用户已批准“许可与运行区分”要求提升为必须修正，保持三种选择语义与布局。

|问题|根因与修复|RED→GREEN及最终证据|
|---|---|---|
|R1|仅claim耗尽分支归类pending，worker通用fail直接终态会留下pending；提取共享settle_failed_items，在claim和fail的已持有管理员/Job锁及原lease围栏事务内仅处理pending|真实run_job：第一项成功后外层目录锁异常，临时3次耗尽/非临时一次失败原均(1成功,0失败,1pending)，修后(1,1,0)，旧任务不重做，失败可新preview/retry；旧lease不能归类新workerpending。SQLite完整771/57；真实隔离MySQL批次/jobs18通过|
|R2|首次restore GET成功前无独立taskId、失败后无重查入口且未发processing围栏；新增restoringTaskId，读前即围栏，失败保留只读重查/详情入口，未明确结果前禁止新POST|首GET网络失败→按钮禁用/processing保留→重查成功→终态完成/解除围栏，整个恢复过程无POST；仅明确404 free_batch_missing允许释放旧跟踪|
|R3|依赖Pinia私有Symbol描述在production变空，退化isolated共享作用域；直接useAdminStore公开API，scope随真实身份变化，请求以身份代际围栏|真实Pinia两管理员、身份切换/卸载后的迟到接受响应、旧身份restore迟到回调均不能回写旧跟踪；NODE_ENV=production专测5通过/4按名称过滤跳过|
|R4|按钮承诺“开启”与SDK固定关闭冲突；普通主按钮“同意并登录，允许统计”/“登录并允许统计”，次按钮“不允许统计”，统计来源仍“登录后再选择统计”|首次、已确认普通登录及收藏按需三个展示断言原失败，改后通过；原true/false/close三个回调语义及布局保持，文案不承诺运行|

最终命令与结果：

- API：`PATH=<node>:<ffmpeg>:$PATH .venv/bin/python -m pytest -q` → **771 passed,57 skipped**；`ruff check src tests migrations`、`mypy src`通过（95源文件）。真实新建socket MySQL仅juya_verify，`pytest -q tests/test_free_access_batches.py tests/test_jobs.py` → **18 passed**，自有实例已停止。原完整MySQL821/4、Redis1为主体实现阶段已归档证据，本轮未重复整套MySQL。
- admin：`pnpm check`、`pnpm test` → **63文件322通过**、`pnpm build`通过。`NODE_ENV=production pnpm exec vitest run tests/unit/features/learning-access/free-batch-controls.spec.ts -t 'two real Pinia|late acceptance|old-owner restore|failed first task GET'` → **5 passed,4 skipped**（-t筛选）。生产测试用真实props事件监听器，避免VTU生产模式不记录emitted造成的测试观察差异；未放宽行为断言。
- mini：`pnpm check`、`pnpm test` → **137文件829通过**；`pnpm build:h5`、`pnpm build:mp-weixin:local`及主包预算通过，20页/三Tab，source483801B、剩余1516590B。测试/生产旧开关不能装载SDK的真实编译契约仍通过。

最终持久证据在本轮SDD工作区fix-report.md与fix-*日志：R1、R2/R3、production Symbol分支及R4均保留实际RED与最终GREEN。旧带green名字的中间production试验曾因VTU emitted观察差异失败；当前最终凭据为fix-admin-production-final.log，文件名不替代断言结果。独立交接总数和修复范围亦已写入三仓HANDOFF，不依赖忽略目录才能理解。

原生Chrome125%、微信物理真机、真实友盟网络/接收仍未验；此前35份视觉/中心测量和2项真实API/dispatcher/worker/H5联调保留，未宣称本修复波次重做。此轮未新启浏览器、CUA或原业务服务。政策bundle与原私有配置保留决定不变。
