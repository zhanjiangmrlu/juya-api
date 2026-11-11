# 2026-11-10 CHG-0040 独立许可能力

本地test已实现新协议版本/确认及账号统计许可接口、0027扩展迁移和五类事件隔离验证。默认legacy必要登录，所有实际统计接收关闭。独立临时MySQL22项通过，SQLite全量751通过/55条件跳过；SDK与真机状态不标记完成，没有推送、部署或迁移真实业务数据。契约见chg-0040-privacy-contract.md，最终验证见../verification/chg-0040-privacy-api-20261110.md。

---

# 2026-11-09 整合08生产后端发布

用户明确授权先备份生产数据库、升级0026并部署release后端。服务器／本机数据库及配置双份校验后，0025→0026／contract3，固定b36fc5a官方CI763通过／3项SQLite专属跳过及双镜像成功；生产7服务healthy、零重启／OOM。55张原业务表原字段、行数及逐行摘要三阶段保持，其余12容器不变；恢复流量后普通游客首页、词汇及听读列表200，个人接口401、角色隔离404通过。维护配置完整移除。已有微信生产包1.0.2／102未重复上传，真机扫码本轮未新增。见[生产记录](../verification/integration08-production-release-20261109.md)及同名无密钥JSON。

---

# 2026-11-08 整合08测试发布

用户追加授权后，三仓test推送、测试双API及配套Worker／独立听读和后台部署完成；官方CI763通过／3项SQLite专属跳过，schema0026／contract3无迁移，原业务数据及生产保持。微信开发版1.5.0-test.20261108.071926上传成功，体验版用户手动切换。以[发布记录](../verification/integration08-test-release-20261108.md)和无密钥JSON回执为准，下方仅历史阶段。

---

2026-11-01 整合06修订17：三端在codex/revision17-integration06隔离分支完成主要实现及分任务审查，最终整体独立审查Approved，交付证据核对完成。API542通过/40跳过、MySQL全marked37通过；后台233与小程序427及检查构建通过。旧主题层和N/M退出、逐项免费/直接分类/可选词汇上线于隔离代码。原运行环境及业务库未切换，无合并/推送/部署；详细范围及未验项见docs/handoff/revision17/integration06/README.md。

2026-10-18 CHG-0015测试部署完成：后端8d4e665、后台6bedc86、小程序3b8210c已推送test。修复CI缺少FFmpeg后39138543235全部181项通过，两角色镜像均成功。共享测试库受控迁移0013，原CLI构建/身份/发布/健康/回滚及保留流程完成两API与后台发布。六容器均为8d4e665、healthy、重启/OOM零；公网两API ready、后台HTML及4个入口资源匹配构建，两个运行中契约匹配源码。Chrome登录与新字段/入口检查及部署Worker隔离四格式/MP3/Range/长静音AAC/版本隔离回归通过。微信开发版本1.5.0-test.20261018已上传，未设体验版、未提审或正式发布。未部署生产，真机验收仍待进行；并行local-share修改未纳入。详细机器证据和交付边界见docs/verification/rev13/test-deployment-20261018.md及同名JSON。

2026-10-18 CHG-0015测试发布进行中：三个功能提交已推送test。首轮CI39138212205发现Ubuntu测试机未安装FFmpeg，新增真实转码测试因此71项失败；镜像构建和服务端部署均未开始。补齐quality任务的FFmpeg/FFprobe系统依赖后重跑，保持真实音频测试，不跳过或弱化断言。后台干净发布副本检查、63项测试及测试API绑定构建通过；微信开发者工具已上传测试包1.5.0-test.20261018，源码3b8210c，非提审/正式发布。

2026-10-18 CHG-0015双标题/四音频/修订13开发完成并待真机验收：三个仓库统一增加英文标题版本链路、DOCX元信息及冲突核对、原件保留与完整MP3播放副本、旧音频重新发布门禁；小程序五档实际倍速、字号/缺项隐藏、U07紧凑布局和U06居中已实现。沿用多ZIP队列隔离及恢复。后端本批174通过/7外部依赖跳过，真实MySQL完整177通过及审查修正后24通过，真实Redis/Celery1通过；后台63、小程序50及完整检查/构建通过。Chrome实际五档进度测量生效，候选/发布隔离、账号状态及布局联调通过；一次独立审查3项发现均补回归修复。并行local-share文件保留且不属于本批提交。详细N01—N29证据与0013发布顺序见docs/verification/rev13/acceptance.md。iOS/Android微信真机播放、倍速和原生视觉验收仍待进行，未推送、合并或部署。

# SDD ledger — plan: docs/superpowers/plans/2026-10-17-rebuild.md

2026-10-18本地提交前复核：用户要求提交代码，本轮管理后台／必要管理API、迁移0012及ZIP文件名修复统一整理为两个仓库的本地提交。最新后端150通过／7外部依赖跳过，Ruff检查／格式及mypy47模块通过；前端59通过、完整检查与构建通过。两端管理契约语义一致，小程序契约无差异；此次不推送、不部署。以下未提交说明保留为此前阶段的历史状态。

2026-10-18后台批量操作与上传优化已按批准方案完成本地开发，未提交、推送或部署。新增管理批次／逐卡结果和素材来源迁移0012；管理列表最多10条、版本原图、批量下线／软删除、全局排序冲突、真实上传阶段及音频替换恢复。后端142通过／7外部跳过，前端57通过及完整检查／构建通过。独立MySQL24项与管理9项、边界2项复验及真实Redis/Celery1项通过；最终真实Chrome→管理API→独立MySQL／Redis／Celery Worker联合验收6项全通过。独立复核问题均补回归修复，无剩余重要问题。详细证据、边界和T114—T137对照见docs/implementation/admin-operations-progress.md及后台docs/verification/admin-operations-20261018.md；旧记录仍作为历史保留。

## Status

Task 1: complete (auth and independent entrypoints; real MySQL 8.4 migration and concurrency verified)
Task 2: complete
Task 3: complete
Task 4: in progress — durable jobs, async media, controlled speech, recoverable imports, ordering/batch and matching admin UI implemented; runtime decoding and remaining import hardening/acceptance continue
Task 5: admin screens implemented through advanced import/sort/batch/speech; final revision12 visual and branch review pending
Task 6: mini core, controlled speech and native three-choice return barrier implemented; actual WeChat device acceptance pending
Task 7: old SQL/runtime/local backup reset done; new deployment foundation, CI and CLI implemented; actual image build/deployment, OSS reset and operations acceptance pending
Task 8: final integrated review/acceptance pending

## Pre-flight

- Auth identities/sessions -> all API operations: separate role and app factories, shared persistence
- Stable card/version -> favorites/learning/resources/imports: shared stable ID; candidate and published version separate
- Completion -> both frontends/admin statistics: single shared transactional service
- API schemas -> frontend clients: generated OpenAPI; no legacy contract compatibility required after reset
- Shared migration -> independently deployed APIs: expansion-first migration, independent release tags

## Rulings

- Ruling: native worktree tool returned `Not a git repository` for the multi-repository root; use manual sibling Git worktrees for admin/mini/CLI and a new backend repository — preserves original main branches without creating an artificial parent repository — worktrees are not managed attachments in the app
- Ruling: referenced shared parent AGENTS.md does not exist in this supplied workspace; use the approved spec and applicable individual repository conventions — newer user requirement overrides obsolete four-tab behavior — any missing additional historical conventions remain unverified
- Ruling: old business code/tests will be replaced rather than kept compatible; original Git history remains intact — explicitly authorized full rebuild — old binaries cannot be restored against the new empty schema

## Environment

- Backend source: /Users/lubi/Desktop/juya/github-repos/juya-api
- Frontend worktrees: /Users/lubi/Desktop/juya/.worktrees/juya-admin and juya-miniapp
- CLI worktree: /Users/lubi/Desktop/juya/.worktrees/juya-cli
- System lacks Docker/uv/Node on PATH; installing isolated tools and using bundled Node; MySQL verification can run remotely once authenticated
- SSH ED25519 first-use fingerprint recorded: SHA256:1JOgC3coZdjNyB0/jmIr8jAD3E3Bm1vi9/g4efHfkEo
- Default local SSH key is not authorized; account file supplies password and a Windows-only key path; attempting supplied password with verified recorded host key

## Foundation evidence

- Initial authentication suite failed because the new entrypoints did not exist; 10 local behavior tests then passed
- Real MySQL concurrency reproduced duplicate login result insertion, then a duplicate-insert lock upgrade deadlock; atomic no-op upserts fix the actual locking boundary
- Login reservation now precedes one-use code exchange; 4 concurrent identical attempts return one token and redeem code once
- SQLite transaction control explicitly owned by SQLAlchemy to preserve rollback across savepoints; invalid-code retries never return a false successful login
- Ruff and mypy pass; fresh Alembic 0001 creates an empty schema, no administrator or business fixtures
- Reset guard tests reject unrelated/new containers, volumes and application databases

## Legacy cleanup

- Executed authorized inventory-bound cleanup: 8 exact legacy containers, 3 volumes (old MySQL/Redis/imports), four backup directories removed; old runtime profile paths retired
- Provider configuration preserved root-only at /root/juya-rebuild/preserved-config
- OSS list versions and multipart both return 403 AccessDenied (EC 0003-00000001); async request sent for corrected bucket/account permissions, not treated as zero objects
- Ruling: do not substitute unrelated cloud credentials after OSS AccessDenied; continue independent local/DB work — prevents accessing the wrong account — OSS reset and real storage deployment remain pending

## Task 2 evidence

- 12 feature assertions initially failed on missing content/media APIs (role isolation already passed)
- Published content is an immutable version; edits stay in the candidate; preview binds revision+hash; stale writes, deleted-card revival and mixed resource references rejected
- Source binding uses explicit UTF-16 ranges for client interoperability; whole-word candidates, manual inflection binding, invalid and overlapping ranges validated
- Real PNG decode/thumbnail, PCM WAV inspection and authenticated byte-range streaming tested locally and with real MySQL
- Native image/audio URLs use opaque 5-minute tickets tied to the actual mini session, current card/version/media; logout and offline revoke subsequent reads
- New migration 0002 verified from an empty MySQL 8.4 schema; Alembic check reports no model drift
- Full real MySQL suite: 32 passed in 86.39s; local: 29 passed, 3 MySQL-only skipped; Ruff/mypy clean
- Ruling: initial media processing is synchronous in Task2; Task4 will move expensive media/import/TTS work behind durable workers before release — avoids shipping a temporary non-durable BackgroundTasks path — interim upload calls are blocking
- User directed rechecking account-related.txt; its explicitly supplied Alibaba AccessKey also returns AccessDenied for both known bucket names. No extra key was requested or printed in logs.

## Task 3 in-progress findings

- Local suite after learning/profiles: 48 passed, 4 real-MySQL-only skipped
- Actual MySQL reproduced two concurrent card completions colliding on the same checkin day despite a user-row lock: the default repeatable-read snapshot was created during authentication
- Fix: explicit READ COMMITTED plus actor serialization; coherent statistics take a shared actor lock. The reproducing concurrency test passed after the change
- Actual commit-failure injection initially received HTTP 200 before persistence; fixed every database yield dependency to function scope so commit finishes before any success response starts
- Durable operation results are now encrypted JSON strings; operation request fingerprints are keyed HMACs so known phone values cannot be guessed offline from a plain body hash
- Source/generated-ID defaults excluded from idempotency fingerprints, so replaying the same raw card request never regenerates identities
- History thumbnails have a separate, ownership-checked resource purpose; neither a last-published original nor audio becomes accessible after deletion
- Task3 tests cover phone/WeChat atomicity, no contact removal, separate versions, no identity merging, encrypted persistence and operation recovery

Task 3: complete — full MySQL8.4 suite 52 passed in 182.92s, including fresh migration0003, concurrent identities, different-card completion race and commit-failure rollback; local 48 passed/4 MySQL-only skips; Ruff/mypy clean

Ruling: implement core admin/mini screens now before advanced imports/TTS tasks — follows the user-approved end-to-end sequence rather than finishing all backends first — generated contracts may expand when advanced features land

Contract integration: response whitelists now generate separate typed APIs; mini list uses page-wide queries for learning/favorite flags and the published admin preview never selects the editing candidate. Three new behavior tests failed then passed; unique OpenAPI operation IDs also tested (HEAD routes remain available but hidden from SDK). Local suite:52 passed/4 MySQL-only skipped; Ruff/mypy clean. Settings repr excludes all credentials and connection URLs.

Admin integration contract follow-up: management rows now identify the published title/thumbnail while retaining the separate candidate. Upload budgets are returned from environment configuration. Both behaviors were RED→GREEN; latest local backend suite54 passed/4 MySQL-only skips; targeted real MySQL contract suite6 passed in22.57s.

Task5 core in progress: rebuilt admin source in isolated worktree with generated schemas, Pinia cookie/CSRF session, explicit retry keys, XHR upload byte progress, full manual editor and source selection, immutable preview/publish, offline/delete confirmation, read-only users/records and A07.10 behavior tests initially passed; browser uncovered publish success navigation blocked by its own busy guard. Added regression RED→GREEN; now11 frontend tests pass. Vue typecheck and production build pass. Actual browser via CUA at localhost verified login→private PNG/WAV upload→save→preview→publish→list and separate saved candidate vs current publication; true empty users/one published card reported by A07. Advanced import/TTS/batch/sort are still pending, so Task5 is not complete.

Ruling: use CUA for all browser actions per its tool instructions; Playwright E2E source is checked in for later user/CI execution but not claimed executed in this session. Browser screenshots under admin docs/verification; local synthetic credentials/media stay outside Git in workspace .private. Local admin API uses a separate SQLite-only verification database, never production or cloud data.

Admin core committed as c5fa1ae in .worktrees/juya-admin. Fresh full checks pass: pnpm check,12 frontend tests, production build (no large initial bundle warning after limiting ElementPlus registration). Added malformed-JSON response regression RED→GREEN: a truncated successful write is reported as unknown and retains the operation key. Browser also verified statistics→published filter and unsaved-leave continue/discard paths. Core phase committed; imports, sorting/batch and pronunciation remain outstanding.

Task6 preflight: mini dependencies installing under Node22/pnpm11.25. Preserved AppID manifest only, then removed obsolete source/tests/build adapters in isolated worktree. New two-tab structure and generated mini contract directories created; implementation not started. Manifest version1.5.0 and production URL checking enabled. Existing main checkout retains all former source/history.

Task6 foundation in progress:14 meaningful session/audio/operation tests now pass (all RED→GREEN). Pure ports isolate only native WeChat/network/audio boundaries. Login waits for user consent; lost responses reuse the one-use code and key; stored token restore never silently re-identifies. Audio priority, pause/seek and late-result disposal tested. Pending write metadata stores keys/paths only, not phone/WeChat bodies; replay keys survive unknown responses and results can be queried. Added old-account late-response regressions (logout or account switch cannot revive/apply old personal data or clear the new account's pending write). UI/runtime adapters not yet built. Current mini test command warns about Vite CJS config; resolve during build configuration work.

OSS account file has not changed. A prefix-filtered bucket inventory using the same explicitly supplied account credentials also failed; this does not resolve the existing AccessDenied blocker and no cloud deletion has been performed.

Admin follow-up underway: requirement13.1 explicitly requires unsaved confirmation before logout. Added root UI regression that failed on a premature logout request; now wiring the editor's existing three-choice leave dialog into a logout guard. Must finish verifying/commit this small follow-up before continuing mini UI. Current admin API/Vite development processes remain running at127.0.0.1:8001/4173; CUA adminTab is in /users; temporary1360x900 IAB viewport override must be reset eventually. CUA browser runtime is initialized, so after compaction call cua.rewriteDocumentation before browser work.

Admin logout follow-up complete and committed in admin worktree:13 tests, full pnpm check and production build pass. CUA actual browser confirms logout opens the editor leave dialog before revocation and Continue keeps session/input. Forced session expiry still bypasses the prompt and clears sensitive UI. Editor navigation and logout share a single coalesced leave decision.

Task6 current state:20 tests pass, including contact field atomic payload/no removal, safe login return targets, and exactly two bottom tabs. ESM package mode removes the Vite CJS warning. Generated mini SDK updated for authenticated avatar upload budget and favorite-list state flags (new backend integration assertions RED→GREEN). Platform uni HTTP/upload and voluntary WeChat adapter, Pinia account store, page shell, privacy/login, learning list/statistics and favorites pages are now written. Secondary scene/records/profile pages and native/H5 build verification remain pending. Mini worktree remains uncommitted during this core phase; missing registered secondary pages mean the application is not yet buildable. Do not claim UI completed.

Task6 detail phase:21 tests pass and Vue typecheck passes for current written files. Learning/favorites lists preserve already loaded DOM during refresh; published detail supports confirmed-range highlighting, whole audio, favorite/cancel, atomic completion, unknown-result query, stale-version/offline/deleted states. Word TTS actions deliberately await Task4 service. Backend now exposes actual decoded audio_duration in published detail (new RED→GREEN integration test). Registered profile/records files still missing; no full build yet.

Ruling: implement U04 as a full-screen movable-image overlay page in the native page stack, with parent context held only in memory — native WeChat previewImage cannot be programmatically closed (official DCloud compatibility table says closePreviewImage unavailable on WeChat), while a dedicated overlay supports system-back close and server-invalidity dismissal; parent onHide keeps audio only for this explicit overlay, onUnload always destroys it — must verify pinch, system back and audio preservation on an actual device. No signed media URL is put in navigation parameters.

Open native issue to resolve during Task6: onBackPress is unsupported on WeChat and enableAlertBeforeUnload alone has a native two-choice prompt. Custom editor back buttons can offer the required three choices; investigate documented page-container return interception or explicitly record the real native limitation after testing. Do not claim all native return paths verified. Root AppPage has a customBack prop ready for guarded account editors.

Task6 all core registered pages are now written: login, learning/favorites, scene detail and image overlay, learning/checkin records, read-only profile, contact and identity editors with custom three-choice leave dialog. Native system-return fallback currently uses enableAlertBeforeUnload and remains an explicitly open gap. Typechecking passed before final build iterations. First H5/MP builds exposed (1) ESM interop of uni plugin default export, fixed using the actual installed module's default factory, (2) empty App.vue script rejected by compiler, fixed by initializing account store, (3) stray closing style tag in generated uni.scss, removed and global CSS moved to styles/main.scss so uni.scss contains injectable variables only. Latest build outputs are pending inspection at /tmp/juya-mini-h5-first.log and /tmp/juya-mini-mp-first.log. Current command session12830 may be complete. Mini App avatar URL typo corrected to actual /me/avatar-url (from backend source). Remaining work includes full formatter/linter/type/build pass, bounded/recoverable async avatar polling when Task4 lands, core browser validation, and advanced features.

Task6 integration follow-up: private local QA verified published list/detail, translation, favorite, completion, records/day expansion, contact validation and masked readback, nickname/avatar save, three-choice custom leave prompt. The QA entry injects only a synthetic local session outside shipping code; WeChat authentication and device gestures are not claimed verified. New regressions cover 5xx retaining operation keys, late-account responses, contact/profile conflict rebase, duplicate login redirects, and record metric switching within the same page. Mini:28 tests and full format/lint/typecheck pass; H5 and 9-page/two-tab MP builds passed before final icon refinement.

Contract recovery follow-up: admin and mini expose actor-scoped durable result queries; generic unexpected errors return a correlated safe500 without raw values in logs. Reproducing tests passed; local backend58 passed/4 MySQL-only skips, Ruff/mypy clean; last real MySQL contract run9 passed. SDKs regenerated; admin13 tests/full checks/build pass. Advanced jobs/import/TTS/sort/batch, native verification, deployment/CLI/load and OSS remain pending.

Task4 in progress: added SQL jobs with encrypted payloads, broker redelivery recovery, five-minute fenced leases, atomic result/side-effect commits and at most two automatic temporary-error retries. API upload acceptance now queues image/audio/avatar processing; decode runs in the Worker. Owner-scoped avatar status and media retry retain accepted upload IDs. Tests were RED→GREEN. Real MySQL jobs/media/fresh0004 suite11 passed in48.96s. Frontend bounded polling regressions pass (admin15 tests, mini30) and full static/type checks pass. Local Celery/Redis execution and browser async-upload evidence remain pending.

Task4 ordering/batch core added: complete published-set digest detects stale/reduced sorting sets, persistent batch/member rows freeze explicit reviewed revisions/previews, and each card commits independently. Partial-failure and original-operation replay tests pass locally. Current backend local67 passed/4 MySQL-only skips; Ruff/mypy clean. Fresh migration0005 and real MySQL batch verification running. No import or TTS implementation yet; Task4 remains incomplete.

Task4 further evidence: real MySQL0006 fresh migration/check and jobs/media/order/batch/TTS suite21 passed in111.27s. Includes four concurrent workers yielding one lease and four different learners sharing exactly one synthesis job. New ZIP/DOCX pure parser9 tests RED→GREEN covers explicit H1 splitting, preserved text/source, path traversal, duplicate/symlink rejection, expansion budgets and forbidden XML entities. No import HTTP workflow or UI yet. Provider documentation checked directly: https://cloud.tencent.com/document/product/1073/37995 and https://cloud.tencent.com/document/product/1073/49575 ; plain confirmed English is used, display IPA is never sent as a phoneme command.

Task4 import HTTP core RED→GREEN: recoverable DOCX/ZIP batches, exact-name media suggestions, staging revisions, confirmation digest, explicit target/version acknowledgement, per-item saves and retry-only-failed behavior. Complete byte-identical objects skip across batches; same names alone never merge. ZIP multi-H1 folders fail independently while valid folders proceed. Shared candidate functions now reject explicit unfinished media references before saving. Local84 passed/6 native-MySQL skips; real MySQL import+fresh0007/check14 passed in33.98s; Ruff/mypy clean. Import template/download, front-end workflow, archive oversized-child recovery and final task review remain pending.

Tencent credentials in the account file successfully returned a synthesis response using TextToVoice/English101050. The local smoke then hit audio_decoder_unavailable because FFprobe is absent on this Mac; do not claim decoded MP3 or device playback passed. Actual runtime decoder/image build verification remains pending. Real Redis/Celery verification setup is in progress on an isolated loopback-only verification container.

Real Redis/Celery verification: isolated authenticated loopback-only juya-rebuild-redis-verify (Redis7.4.11,80MB) and a separate local Worker process processed an already-committed upload after delayed dispatch. Broker envelopes contain only job IDs; duplicate delivery completed once with attempts=1. Actual integration test1 passed in3.45s. The initially requested8.2 image could not be pulled; reused the server's existing maintained7.4 image for verification. Production image pinning is still pending.

Front-end advanced work in progress: generated SDKs now include imports/batches/order/TTS. Mini pronunciation loader bounded/cancellable, words call controlled references and show source lines; backend full MP3 decoder runtime still pending. Against source7.1/7.3, corrected an integration mistake: translations must be a complete block below all English, not interleaved per line. Both clients have RED→GREEN page tests for this. Admin read-only preview now uses gesture-resumed WebAudio, pauses whole audio without resetting position and ignores late prior-word results (new regression). A03 offers explicit Save and audition for unsaved content, with candidate-only save; old online content unaffected. Frontend full checks/builds are running; browser advanced-flow verification, sorting/batch/import UI and native return handling remain pending.

Advanced frontend verification: mini33 tests (including ordered complete translation and cancellable controlled pronunciation), full static/types and H5/MP builds pass. Admin18 tests, full static/types and build pass after wiring preview and inline Save and audition; WebAudio handles delayed generation after the initial gesture. Native system-return gap remains open: reviewed official page-container documentation https://doc.dcloud.net.cn/uni-app-x/component/page-container.html and standard uni-app lifecycle https://uniapp.dcloud.net.cn/tutorial/page . WeChat onBackPress is unsupported; page-container consumes native return. No page-container interception code or true-device proof yet. Do not claim this gap resolved.

Template/single DOCX follow-up: the authenticated static example download now contains a parseable one-card DOCX, freshly drawn scene PNG and actual Tencent-generated2.65s WAV matching the sample dialogue. Build script accepts a reviewed local audio asset and never embeds provider credentials. This WAV decoded successfully; production/default MP3 runtime validation is still pending. Single-card editor imports are staged in hidden-from-A04 single-mode batches and reject multi-H1 DOCX with single_docx_multiple instead of taking the first card. New tests RED→GREEN; import suite15 passed. Fresh backend full suite86 passed/7 external-only skips; Ruff/mypy clean.

Admin upload cancellation regression RED→GREEN: AbortSignal stops only transport, returns an unconfirmed acceptance state and retains the fixed operation key for recovery/retry. The upload client also treats malformed successful responses as unknown. Admin now19 tests; full checks/build after the latest cancellation/example-SDK change are pending. Frontend pronunciation/async-media/whole-translation work remains uncommitted; backend is committed through980c206 with template/single changes pending.

Commits: mini772e4e2 (async media, full translation, controlled word speech); admin25d008a (async uploads/cancel, controlled WebAudio/preview/inline Save and audition, full translation). Admin core19 tests/full checks/build were green. Task4 admin ordering component now written and wired to the existing list: full published set, thumbnails, drag/up/down, stable replay/query keys, unknown-state edit lock, conflict rebase, three-choice leave/logout guard. Two meaningful regressions RED→GREEN cover preserving rejected local order and following the latest official order on a clean refresh. Latest admin21 tests/full checks pass; browser sorting proof and batch/import pages still pending. Backend catalog-order now bulk-returns thumbnail_id; the new HTTP assertion passed, but the small follow-up is not yet committed.

Task4 late race fixes: publication acceptance now records a soft-deleted reviewed member as its own failed job while other selected members can publish. Failed retry revalidates the same reviewed revision before enqueueing; obsolete reviews remain failed until rechecked. New regressions RED→GREEN. Actual server speech codec is configurable (defaultMP3) and participates in cache identity; local QA deliberately selects WAV because this Mac lacks FFprobe. Latest backend89 tests/7 external-only skips, Ruff/mypy clean; real MySQL order/batch/TTS10 passed in62.02s.

Local verification stack restarted with isolated SQLite, genuine Redis/Celery Worker and dispatcher, admin4173/API8001 and mini5174/API8002. Redis uses a dedicated verification database1 for the live UI; queue integration tests use database0. Provider credentials remain only in backend process environments; Vite receives no JUYA settings. Parent process is launched by .private/redis-test.py -> .private/run-local-stack.py (exec session23928); PIDs recorded privately. Actual CUA admin preview reached coffee playing state after a real cache-miss task and cached replay; screenshot docs/verification/admin-pronunciation.png. This is WAV/browser evidence, not WeChat MP3/device proof.

Admin selection/batch UI now wired (uncommitted): cross-page max50 selection, current-eligible prechecks/previews, explicit review checkbox, resumable results and retry/recheck-failed actions. Recent10 batch results appear inside the card list with a bounded visible-page background refresh. Admin22 tests/full static checks/build passed before the latest live UI work. Sorting/batch browser acceptance is underway; current adminTab1 at /cards/new holds unsaved synthetic example-card input while audio decoding is in progress. Do not reload this editor until its candidate is saved or explicitly discarded. Current2nd QA card title: 咖啡店点单（批量发布验收）, dialogue Ivy/Could I get a latte, please?/请给我一杯拿铁。, word latte/拿铁咖啡, image and actual2.65s WAV from private example fixtures. A03 pronounce button should also be disabled while media uploads/processing; implement after this live draft is saved to avoid HMR destroying in-flight child state.

Task4 latest: actual CUA batch acceptance published both reviewed cards through Redis/Celery, then restored the same durable result from the recent entry. Full-set ordering moved the new card above the existing one; the three-choice Save and leave path committed it. Mini list reflects that order and retains the original stable card's completion and 1-card/1-day statistics. Admin/mini controlled word WAV playback reached playing. Screenshots saved in both frontend repositories. Admin cancellation UI now retains old media, queries the fixed receipt before retransmission, and exposes stop/cancel; regression RED→GREEN. Confirmed 410/422 publication rejection no longer claims unknown acceptance. Admin24 checks/tests/build passed before imports UI work.

Import follow-up: actor-scoped batch_id card filtering and retained-file retry endpoint added; single-card batches reject non-DOCX uploads. New behavior tests RED→GREEN, local full backend90 passed/7 external-only skipped; real MySQL import suite16 passed in53.59s; Ruff/mypy clean. Admin same-page three-step import UI, persisted staging with late-edit/unknown-receipt protection, explicit target comparison and asset selection are now wired. Admin27 tests/full checks/build pass. Real CUA mixed ZIP returned one complete, one incomplete and one unreadable multi-card folder; leave/resume preserved both edited names and explicit update target. Formal cards were unchanged before step-three confirmation. First actual two-item save is currently processing; browser result/filter proof and import/single-DOCX/voice hardening are ongoing.

Local verification stack restarted for these APIs; parent exec session31321 replaces23928. New PIDs recorded in workspace .private/local-stack-pids.json. Live admin currently at /imports?batch=3e7d2d2e-1d23-4611-a1e8-92b174f16d8e, first save already accepted; inspect result rather than submit again.

Task4 import end-to-end evidence: the accepted mixed ZIP saved two actual drafts (one explicit existing-card update plus one incomplete new card), with one unreadable folder. Batch-filtered A02 lists exactly those two; the existing publication remains unchanged. A03 single-DOCX UI rejected multiple H1 cards, then previewed a legal candidate, explicitly replaced only dialogue/vocabulary/chunks and persisted the retained hand-written title. CUA screenshots in admin docs/verification. No unsaved editor remains open.

Controlled import-staging speech now uses owner/batch/item/revision/word references, shares the synthesis cache, creates no Card and rechecks staging revision on every audio request. New grant revocation and arbitrary-text rejection tests RED→GREEN; real browser staging audition reached playing/replay. GET revision validation now returns422 for zero. Individual oversized/corrupt ZIP members persist their own safe error via additive migration0008; readable text and sibling folders survive. New oversized-image regression RED→GREEN. Import thumbnails now use processed thumbnails and unreadable vs excluded counts are distinct. Backend local92 passed/7 external-only skips, Ruff/mypy clean; actual MySQL import+speech+fresh0008/check24 passed in98.80s.

Admin latest29 tests/full checks/build passed: full three-step import, independent per-card staging, late typing/unknown-receipt retention, target diff selection, bounded file processing/results, actual per-item saves/retry confirmation, recent resume, asset pickers and explicit single-DOCX text replacement. A target confirmation is invalidated if reviewed content changes. Upload, review-list, target/asset pickers and save results are separate components. Whole-branch review and complete visual QA still pending.

Local stack latest restart: exec session51210 replaces31321; APIs now include0008 and staging speech; PIDs private. IAB admin tab1 is /cards (saved synthetic data only), mini tab2 remains the new published-card detail. Viewport override reset. Account file mtime is1792216641 (13:57); reviewed added RAM section safely: login/short incomplete AccessKey field does not provide a usable full OSS key pair. Prior403 is not treated as empty buckets, and no further repeated permission request was sent.

Mini native-return implementation: shared guard now uses a built-in WeChat page-container barrier, re-arms after system return, waits for afterleave before approved navigation and stays put on missing acknowledgement. Unsupported component capability blocks starting edits rather than falling back to an inadequate two-choice confirmation. Both account editors wired. Three platform-event regressions RED→GREEN; latest mini36 tests/full checks and H5/MP builds passed, compiled WXML verified with the native tag/events. Physical right-swipe/Android return, zero-height barrier interaction/scroll and actual wx.login still require device acceptance. Sources: https://doc.dcloud.net.cn/uni-app-x/component/page-container.html and https://uniapp.dcloud.net.cn/tutorial/page ; direct WeChat docs unreadable in browser.

Runtime preflight: server cached verification image has Python3.13.13, /usr/bin/ffmpeg and /usr/bin/ffprobe. It will be used only for isolated codec verification, not as the new production business image. Server root disk40GB,13GB free. No gh CLI or new backend remote configured; new CI/image release workflow and CLI still pending. Current backend uncommitted codec hardening has RED→GREEN tests rejecting truncated PCM, metadata-only success when full decode fails and playlists before decoder invocation; targeted16 passed/1 MySQL-only skip, Ruff/mypy clean. Real compressed codec verification is next.

Codec verification passed: actual Tencent MP3, WAV and FFmpeg-derived M4A/AAC decoded through the new module in an isolated network-none/read-only/memory-capped Linux container. Durations2.628/2.650/2.650/2.752s; truncated PCM rejected. The first attempt hit file permissions because the cached image runs nonroot; corrected only fixture/source permissions inside the scoped mount while retaining the root-only parent. No cloud key or DB configuration mounted. New decoder requires full compressed decoding with explicit allowed demuxers/protocols/deadlines and verifies PCM frames. Full backend95 passed/7 external-only skips, Ruff/mypy clean. Report: docs/verification/audio-codecs.md. New production image/build/CLI still pending.

Task7 queue isolation added: role-filtered SQL dispatch/claim, separate juya-admin/juya-mini Celery queues and an explicit Worker/dispatcher role required outside local verification. An incorrectly routed task is not claimed or charged an attempt. RED→GREEN owner isolation test; local backend96 passed/7 external-only skips, actual MySQL jobs6 passed in31.84s, actual role-scoped Redis/Celery Worker test1 passed in3.08s; Ruff/mypy clean. Local shared verification stack still deliberately runs role=None in local mode; deployed environments will have separate role processes.

Build preflight: Mac can retrieve official Docker Python3.13.16-slim-bookworm metadata. Index sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641, Linux amd64 manifest sha256:f040863673aea2570c3ff6a5c3fb4c673a016cbc5375005ad145915922b6b78a. GitHub connector lookup for zhanjiangmrlu/juya-api returns404 (not proof of absence versus app access). No repository was created or pushed. Existing frontend worktrees contain quality-only GitHub workflows; old deploy workflows were removed during rebuild. Do not revive old backend recipes.

Task7 deployment foundation: schema0009 inserts an explicit code/schema compatibility marker; readiness rejects incomplete/old/incompatible schemas and accepts compatible additive revisions. Role images cannot start the other API/Worker. Docker multi-target images pin official Python3.13.16 and contain locked dependencies/FFmpeg/nonroot runtime. CI uses disposable real MySQL8.4+Redis7.4, verifies contracts and builds two private role artifacts; each image receives isolated no-network codec/UID/role verification before export. Artifact metadata binds exact role, commit, config ID and archive hash. New infrastructure initialization preserves generated secrets across retries and separates test/production SQL/Redis/accounts/keys. It has not yet been applied to actual new runtime infrastructure.

Actual ECS Compose config verification passed for all four environment/role selections and separate three-service infrastructure: correct roles and networks, app loopback ports only, no public SQL/Redis ports, no application-owned data volumes. Deployment/compatibility MySQL tests3 passed earlier; full MySQL rerun currently in progress. Latest local backend101 passed/7 external-only skips, Ruff/format/mypy44 modules clean. Actual role-scoped Redis/Celery rerun1 passed in2.09s.

CLI adaptation: both API targets resolve juya-api and separate role recipes; API tags are project:commit and environments remain bound by manifests/runtime preflight/SQL/Redis/OSS configuration. CI artifact validation rejects wrong role/commit/hash/config/platform/source labels before remote checks. Windows/macOS/Linux supported; Node45 tests including real package installation pass on this Mac. Python154 tests pass/10 native Docker/POSIX-dependent skips. Explicit admin migration loads verified image, checks runtime and runs dedicated migration tool without stopping services or changing current/previous links; ordinary publish/rollback does not back up, migrate or restore SQL, and does not select infrastructure or the other API. Legacy release conversion removed. Dispatcher replaces old beat process. README/config templates/Compose fixtures updated; original histories retained.

User supplied git@github.com:zhanjiangmrlu/juya-api.git and explicitly authorized pushing code. SSH ls-remote succeeds for this empty repository; origin added. Private provider-credential audit of all23 prior backend commits found0 matches. Browser GitHub form opened, but Chrome control timed out repeatedly; no browser mutation or account setup performed. Backend branch will be pushed with this foundation commit; production remains undeployed and OSS403 unresolved.

New infrastructure applied onECS: MySQL plus separate test/production Redis healthy, new emptyjuya_test/juya_production databases, independent DML-only application and migration accounts. Verified actual grants and zero tables, then reran setup with unchanged secret-file hash; app account can read aggregate Threads_connected status. No legacy resource was reintroduced. Root-only state at/etc/juya/rebuild and exact new release roots created.

Backendf77d6b0 pushed with user authorization to origin/rebuild-v15. GitHub run39020673487 quality107 passed/1 failed, images correctly skipped: immediate dispatch at a fractional second exposed MySQL DATETIME(0) rounding. Deterministic new regressions reproduced both task availability and Beijing-midnight signup rounding on actualMySQL (2 failures). UnifiedMySQL DATETIME(6) plus expansion0010 fix all timestamp columns; minimum readiness revision10, compatibility contract remains1. Targeted realMySQL+Redis/Celery timestamps/fresh migration/check/readiness/actualWorker/metrics10 passed45.67s; full local106 passed/7 external-only skips; Ruff/format/mypy clean. Previous full actualMySQL run106 passed/1 Redis-only skip572s. No delay/sleep workaround added.

HTTPS generator test config passed actualECSnginx-t with retained real test certificate (expires2027-01-08), no live config replaced. Eightknown domains resolve toECS; production cert not yet provisioned. Safe logs omit URI/query/auth/contact; role-specific prefixes and Range passthrough, oldH5 returns410. Lightweight operations scripts monitor host/container/API/SQL/queue/TTS aggregates; persistent two-sample debouncing and unknown-data retention tested. Actual server collection and firing/recovery dry-run passed; noFeishu notification sent and timer not enabled. Source monitor metrics are passed through stdin to configured API container, not persisted into images.

CI run39021264020:112 passed/1 failed. Task delivery now succeeds; the remaining guard caught Celery's default startup banner including a passwordless CI Redis URL. Inspected installed Celery's globalquiet option and startup-info code; Worker now passes--quiet before worker, retaining warning/error behavior and all log-safety assertions. Actual separate Celery process passed both authenticatedRedis (2.72s) and an additional disposable, loopback-only, no-authRedis verification (2.88s). That extra container was stopped/removed in cleanup; deployed Redis authentication unchanged.

Production certificate issued using the existing ACME account and confirmed four-domain SANs, expires2027-01-15. Only a scoped production HTTP ACME/503 scaffold was installed and nginx reloaded; new application HTTPS vhosts not installed yet. Existing test certificate retained. ECS metadata security-credentials endpoint returns404: no attachedRAMrole available as an alternative OSS credential source. No RAM policy or account permissions changed.

CLI commitb0e51a9 adds two further end-to-end boundary regressions: CI bundle packaging without any local Docker invocation and admin publish/rollback preserving the other role's container identities. Latest Python156 passed/10 native environment skips, Node45 passed. Admin web recipe committed7765ff0; no front-end source change in that commit. Backend push authorization applies to new juya-api repository; frontend/CLI branches remain local pending integration review.

2026-10-17追加：c699a25的GitHub CI运行39021677527全部通过，两个角色镜像已取得。新T01–T113验收映射逐条标出已有证据与真机/OSS/部署等待项，不把待验收写成通过。新增单卡累计文字512KiB约束，超限HTTP回归RED→GREEN；内容/导入27通过，全本地107通过/7外部依赖跳过，Ruff/format/mypy通过。RAM段已按用户指示重新读取，AccessKey ID字段为12字符含空格、无配套Secret，无法用于OSS；已询问其是否登录密码，未展示内容。

2026-10-17独立整体审查已完成，四项Important已补RED→GREEN：下线递增修订使旧预览/排队发布失效；小程序未知结果原正文重试；后台未知创建先收尾再PUT当前修改；DOCX按H1逐卡保存正常结果。后端111通过/7外部跳过，真实MySQL三个新增边界19.27秒通过，后台31、小程序38项及完整构建通过。CUA四卡DOCX实际Worker结果为2成功草稿/2无法读取。新RAM完整凭证已从文件读取，独立测试juya-test仍403，单桶授权文件已备好并询问。用户明确先不处理生产juya，后续仅推进测试OSS和测试发布。c699a25两镜像已在ECS实际非root只读隔离运行通过四种音频解码，OCI图身份匹配；两空库0010迁移已完成且业务/账号/会话均零，未创建管理员或启动新API。新审查修复尚未部署。

2026-10-17最新证据：RAM授权修复后，juya-test实际读写删除通过，按精确清单清除801旧对象版本，复查对象/版本/分片均零。生产OSS及新应用继续按用户要求延后。CI39023597019全部通过。双API665820a及各自Worker/dispatcher已通过实际CLI部署引擎部署到测试回环端口；仅离线初始化新管理员，另有私密清单20个合成压测用户，不作为微信登录验收。测试Worker原0.15/0.2核造成10秒探针超时，实测依赖导入0.15核31.799秒、0.5核6.467秒；改0.5核、保留低CPU shares，Worker探针上限改30秒覆盖冷启动竞争。

真实OSS图片/缩略图/音频后台处理及卡片整体发布已通过。Range正文中断追到SDK StreamBodyReader.read不支持size参数；三个真实SDK类型回归先复现TypeError，再验证有界迭代及关闭。本地114通过/7外部跳过，Ruff/format/mypy通过。修复镜像、HTTPS、20并发和独立回滚仍在执行，尚不声明通过。此前403/尚无管理员/尚未启动API段落为历史过程记录，以此最新证据为准。

测试运维补充：实际管理API665820a→c699a25→665820a回滚/恢复成功，小程序三容器ID/镜像/启动时间保持不变，124次合成用户学习写入全部成功，无数据库迁移或恢复。首轮20并发混合学习420请求全200，20卡DOCX实际OSS导入7.071秒完成，但P95为1690.89ms，未达500ms目标。此轮通过SSH隧道，CPU配额为旧测试mini0.3核；已配置admin0.4核/mini0.8核，等待5877416修复镜像部署及HTTPS复测。

监控新增显式--environment选择，回归确保测试采集不会探测延后的生产容器或端口。ECS测试SQL聚合可用、告警两次异常触发/去重/两次正常恢复实测通过；仅test的systemd覆盖配置及timer已启用，通知未启用且未发送Feishu消息。本地115通过/7外部跳过，Ruff/format/mypy通过。API修复提交5877416的CI39025440990全部成功。

2026-10-17测试交付最终更新：两API5877416、后台6add0ac已通过实际独立CLI引擎发布并启用测试HTTPS。真实OSS Range/Tencent MP3、鉴权/撤销/旧预览和版本校验通过。20并发HTTPS420业务请求全200，P95402.44ms，同时20卡导入7.502秒。新管理API实际rollback→publish期间小程序三容器身份不变、93次学习写入全成功。无OOM/自动重启；mini Worker交付内存由256增至384MiB，原始内存事件oom0。测试监控启用、未发通知。合成测试数据及6个OSS对象按清单清除，保留管理员；最终HTTPS用户/卡片/统计均0，旧测试Token401。生产继续暂缓；微信真机、线上视觉、双环境同机压测和通知仍待验收。详见docs/verification/test-rollout-20261017.md及对应JSON，以此最终状态替代此前进行中记录。

2026-10-17本地导入恢复：用户上传约7MiB ZIP后任务一直queued/attempts0；本地验证Redis SSH隧道进程已退出，Worker重连耗尽退出，API仍可接受持久任务。已以独立进程恢复固定本地端口的队列连接和Worker/dispatcher，增加SSH keepalive、断线重连与子进程重启；这些本机验证配置保存在工作区私密目录，不进入发布包。原ZIP随后成功解析，继续暴露流式WAV的RIFF及data长度均为0xffffffff，被既有“明确长度必须完整”校验误拒绝。现在仅对此双未知长度标记使用有界上传字节计算解码长度，普通声明长度及完整采样帧校验仍保留；不改写保存的原音频。ZIP资料扫描忽略__MACOSX、AppleDouble及.DS_Store，所有成员仍先经过原安全/展开限额检查。两个成功用例修改前实际失败，修复后通过，另有未知长度残缺采样帧拒绝回归。本地全套118通过/7外部依赖跳过，Ruff/format/mypy通过。精确修复未保存、revision1的当前本地批次，删除仅由隐藏附件产生的候选及关联记录，对真实WAV补偿投递；原数据库先保存私密快照。HTTP登录后读取确认1张可读卡、4份文件全部ready、audio/wav/50.7秒、issues为空。此兼容修复仅本地生效，尚未部署到ECS测试环境，也不作为微信真机播放验收。

2026-10-17增量测试发布完成：后台92152b3、管理API及Worker/dispatcher6aca4f4已经通过原CLI发布引擎上线测试环境。CI39034384687真实MySQL/Redis125项及两角色镜像通过；本次只发布管理侧。新运行Worker的临时库/临时素材ZIP+流式WAV探针通过，真实Redis定向ping通过；未写真实业务库/OSS。线上Chrome登录与导入提示通过，六容器healthy、无OOM/自动重启，小程序三容器与发布前完全一致。无数据库迁移、数据清理或生产发布。详细证据及发布号见docs/verification/test-rollout-20261017.md同日增量记录。

2026-10-17多ZIP测试发布完成：后端e503442、后台5e7e261已提交并推送test，CI39041233684全部通过。原CLI发布引擎先成功迁移0011，再仅替换管理API／Worker／调度进程及后台页面。发布号20261017T143926-e503442bd543-98d7dc与20261017T144627-5e7e261e9a6e-f75743，保留上一应用版本。发布前后端133项／前端42项及完整检查通过；新Worker镜像7项临时库／素材导入回归、实际Chrome公网登录与多ZIP／DOCX入口检查通过。两测试API公网HTTP200／ready，管理三容器healthy且无OOM／自动重启，小程序三容器身份及启动时间保持不变。验证未写共享导入业务数据，未发布生产。详细证据见docs/implementation/multi-zip-import-progress.md测试发布记录。

2026-10-18文件名乱码修复：实际用户ZIP中文路径使用UTF-8字节但未设置语言标记，Python默认CP437读取导致编辑页、导入来源及预览音频名称乱码。新增严格可逆解码，保留原始成员查找键、UUID及素材字节；安全检查同时拒绝解码后重名。新导入保存正确标签，历史导入在返回来源和素材元数据时恢复显示，无需重导或修改历史业务记录。8项回归覆盖新旧记录、正常UTF-8、旧西文编码、成员读取及路径冲突；解析回执记录文件名已归一化，避免合法特殊字符二次解码，旧解析重放保留文件ID及单份卡片。完整后端150通过／7外部依赖跳过，Ruff检查／格式及mypy47模块通过。已重启本地管理API及受本地监督进程管理的Worker／dispatcher；Chrome实际旧卡编辑／预览和已有导入结果确认中文路径恢复，截图位于docs/verification/zip-filenames-fixed.png、zip-source-folders-fixed.png。没有提交、推送或云端发布；线上测试环境尚未更新。工作区其他未提交管理功能修改保留。

2026-10-18后台测试部署完成：已推送后端47fae39、前端2c52cd8；CI39114203966真实MySQL／Redis157项及镜像构建全部通过。首次迁移回执因SSH中断丢失，恢复后只读确认0012已完成、原应用仍在运行，再复用校验和一致的已上传包，通过原CLI校验／锁／部署／健康检查／版本保留流程完成发布。管理API及Worker／dispatcher发布号20261018T091633-47fae395569e-232880；前端发布号20261018T124123-2c52cd864225-9da5d8。管理三容器healthy、重启及OOM均零，小程序三容器ID／镜像／启动时间保持不变。线上HTML和4份入口资源逐字节匹配前端产物，两API公网ready／HTTP200；新Worker以独立临时SQL和素材完成9项乱码、分页、批量管理回归，不写共享业务资料。前端59项及完整检查／构建通过。未发布生产；本轮未重新执行完整线上浏览器业务流程。机器证据：docs/verification/admin-test-deployment-20261018.json。


2026-10-18本地固定域名分享：新增三个dev域名的独立HTTPS Nginx入口与限权SSH反向隧道，业务前端、两API、Redis、Worker和调度在本机运行。用户批准将原0012数据库与素材复制，分享副本升级0013；原数据保留。新增start/status/stop、进程归属验证、首连失败退出、断线重连、三路实例就绪检查及独立小程序分享构建。9项工具测试、Ruff、真实公网登录/上传/ZIP处理/发布/Range/WSS、断线与启停验证通过；独立审查修复转发头继承等问题并复核。恢复工作后使用最新提交重新构建和启动，用户扫码并以手机流量确认登录、卡片、音频均正常，本地后端收到真实微信登录。微信后台设体验版需用户手动选择本次分享上传版本，正式版未发布。详见docs/operations/local-share.md及local-share-verification.md。

2026-10-19本地分享刷新优化：修复开发资源被全局no-store阻止缓存的问题，保留Vite依赖immutable及源码no-cache；启用SSH隧道压缩、后台开发站点gzip和HTTP/2。三轮真实浏览器测量首次7.1～11.5秒、重复刷新约0.84秒，首次传输11.6MB降至2.8MB，文案热更新0.78秒且无整页导航。公网登录/会话/卡片读取/退出及API不缓存、Cookie标记、来源隔离和内部入口隔离通过；9项工具测试及Ruff通过。Nginx备份校验后平滑加载，仅重建本工具SSH隧道；后台业务源码和小程序未改，测试探针文案已恢复。详细记录见docs/operations/local-share-verification.md。

2026-10-19本地H5分享：将dev-h5.juyayingyu.com接入同一分享环境，新增独立H5进程4174及云端回环34174，复用本地8002用户API，保留旧QA5174。新增H5独立模式、开发主机名校验、单独依赖缓存及输出路径、HTTPS证书与SSH四端口精确许可；未注入合成会话。真实公网手机尺寸浏览器6.0秒打开登录页、1.3秒文案热更新且无整页导航，同源API实例与本地相符，QA/内部/管理路径404。H5停止503、start恢复及原入口检查通过；工具12项、小程序51项及完整check、微信独立构建通过。H5现有代码不支持wx.login，登录后业务仍由微信体验版验收。本次不上传体验版；详见docs/operations/local-share-verification.md。

2026-10-19小程序图片500修复：dev-api实际转发到本地分享API；图片地址GET先读鉴权再写MediaTicket，SQLite延迟事务在并发读转写时触发SQLITE_BUSY/database is locked。对共享数据只读快照复现9张卡、4轮并发：修复前36次中32次500，成功图片为正常WebP；修复后36次全部200且实际图片字节有效。SQLite写请求在鉴权读取前使用BEGIN IMMEDIATE预留写锁，普通GET、素材读取及就绪检查保留延迟读事务；签发地址与写审计的管理GET显式标记写意图，schema检查复用当前连接。MySQL事务配置保持原逻辑。新增3项回归覆盖并发签发/读取/退出撤销、持有写锁时普通读取、审计GET写意图；全套189通过/7外部MySQL或Redis环境未配置跳过，Ruff检查与格式、mypy通过，独立审查无剩余阻塞问题。受归属校验的本地管理/小程序API、Worker及dispatcher已重载，Redis、前端、H5和隧道进程保留；没有迁移或清理业务数据。用户当前微信开发者工具切换回学习页后，9个图片地址接口和9张WebP均HTTP200，原失败缩略图显示。诊断快照、探针结果及前后截图保存在工作区私密目录.private/image-url-diagnosis，不提交含会话的数据库与截图。本次只在本地dev分享环境生效，未部署云端测试/生产，未打包或上传体验版。


2026-10-20学习列表内容数量补齐：对照Figma193:1617，原小程序列表接口未提供词汇/语块统计，组件也未渲染数量行。CardBrief新增非负vocabulary_count与chunk_count，从当前已发布版本payload计算，沿用原列表批量读取，不增加逐卡详情请求或数据库迁移；两端OpenAPI及小程序生成类型同步。场景卡在中文标题和学习状态下方按设计展示11px/18.7px灰绿数量行，零值部分省略，不向无效历史卡暴露数量。学习状态仍由真实completed记录决定，未修改成绩。后端Ruff/格式/mypy48模块通过，小程序pnpm check及本地分享微信9页构建通过；本轮未新增或运行自动化测试，只同步已有组件测试的契约数据。仅重载归属校验通过的本地mini进程，其他七进程保留；用户手动完成隐私同意和真实登录后，开发者工具实见戏剧社8词汇/5语块、书评10词汇/5语块，与本地已发布内容一致，零语块卡只显示1个词汇。当前账号完成数0，未展示已学提示；未写入学习记录。私密截图位于工作区.private/scene-card-metadata/local-list.png。用户原模拟器dist/build连接云端test-api，新字段尚未部署云端测试；本轮仅本地分享环境生效，未上传体验版。并行登录页修改保留。

2026-10-20测试后端发布完成：用户授权后将f9fd476推送origin/test，既有GitHub CI39428175138完成193通过/3跳过及两角色镜像构建。通过原CLI发布引擎的归档摘要、镜像身份、发布锁、健康检查和版本保留流程，仅更新测试小程序API及Worker/dispatcher；发布号20261020T132101-f9fd476aec69-62c637，三个容器均healthy、重启及OOM为零。两测试API公网ready/HTTP200，运行中OpenAPI包含vocabulary_count/chunk_count；在新镜像内调用真实列表处理函数只读检查7张线上卡片，数量均与当前已发布版本一致。该检查不等同于经过用户鉴权的公网列表端到端验收，未代替微信真机验收。未执行数据库迁移或业务数据写入，schema保持0013；管理侧三个容器及MySQL/两个Redis身份和启动时间保持不变。生产未发布；小程序上传由用户另一对话负责，本轮未操作。安全汇总见docs/verification/mini-counts-test-deployment-20261020.json。

2026-10-21缩略图与原图按需加载：按用户确认方案，两端封装默认缩略图选择方法；详情接口补充当前发布版本的thumbnail_id，契约与小程序类型同步，无迁移。详情小图直接显示缩略图，与原图状态分离；原图仅点击后请求。微信开发者工具确认getImageInfo返回fail invalid，改由图片组件在预处理失败时直接加载同一授权原图，实际原图显示与125%放大通过。后台列表增加懒加载与失败独立重试。小程序125项、后台72项、后端190项通过，后端7项真实MySQL或Redis依赖测试跳过；两端检查、H5/微信/后台测试构建及后端Ruff通过。隔离合成账号浏览器流程确认520×780缩略图、点击后2000×3000原图，查看前无原图请求，直接刷新详情正常。独立审查无需修复问题，原生故障后续调整另有回归与实测。代码未提交、推送或部署，未上传体验版；测试API新增字段须先发布，未改生产或既有业务数据。详见docs/verification/scene-thumbnails-20261021.md。

2026-10-21缩略图前端补齐：按用户补充“没有缩略图时前端处理原图”扩展两端封装，旧接口缺字段也会等比生成最大360×540小图并缓存，保留完整原图查看。微信getImageInfo对本地下载同样fail invalid，OffscreenCanvas解码/导出路径实测成功；书评详情由暂无缩略图恢复显示，原图查看正常。两端合成API移除缩略图字段后，实际浏览器小图360×540、原图2000×3000验证通过；该兜底首次需要下载原图。审查发现的缩图失败阻断原图、后台跨页持续持有图像均有先红后绿回归并修复，复核无剩余实质问题。小程序142项、后台81项及完整检查、H5/微信/后台测试构建通过。无新增后端行为改动；先前后端190通过/7环境依赖跳过证据保留。代码未提交、推送、部署或上传体验版，无需为缺字段兜底先发布后端；未修改生产和既有业务记录。详见docs/verification/scene-thumbnails-20261021.md。

2026-10-21后台列表小图进一步压缩：用户要求降低约100KB传输并询问链接参数。为现有管理图片接口补充固定thumbnail=list参数，仅鉴权后对ready的thumbnail生成最大144×216/WebP60小图，每实例128项有界缓存；原图和既有素材字节不改，HEAD/Range使用小图实际字节。后台封装sceneThumbnailURL控制列表参数/重试，无缩略图时前端生成规格同步缩小。193项后端通过/7独立环境跳过，Ruff/格式/mypy49模块通过；后台81项及check/build:test通过；只读审查无实质问题。两后台检出同步后，只重载归属和配置验证通过的本地管理API，其他7角色保持原记录。Chrome实际4173七张图144×216、资源7.7–9.7KB（网络含头8.1–10.0KB）；点击查看仍为无参数1024×1536原图，显示和关闭正常。已在本地生效，未提交/推送/云端发布，未改小程序规格或持久业务素材；详见docs/verification/scene-thumbnails-20261021.md。

2026-10-21小程序参数缩图：按用户要求将列表、详情及安全历史摘要的小图链接追加thumbnail=list，复用后台144×216/WebP60，原图与音频地址不加参数；前端缺图生成规格同步缩小。小程序API在既有票据/会话/版本/历史权限校验后才用独立有界缓存；撤登录/下线/撤收藏均不可命中缓存绕过权限。新增回归先红后绿；小程序143项和完整check、H5/微信测试/微信独立分享构建通过，后端195项/7独立环境跳过、Ruff/格式/mypy49模块通过，独立复核无实质问题。隔离合成账号浏览器确认列表/详情144×216带参数、点击2000×3000原图不带参数且关闭恢复正常。仅重载归属/摘要校验通过的本地mini API，其余七角色保留；本地H5及独立分享构建已更新。未部署云端API、未上传体验版，云端参数支持待发布；未修改持久图片或学习数据。详见docs/verification/scene-thumbnails-20261021.md。

2026-10-21提交交付：用户明确要求将本轮代码提交并推送三个仓库的远程test分支。提交范围为小程序、后台及统一API的缩图参数、无缩图前端兜底、原图独立查看和对应测试/契约/记录；私密会话、数据库、媒体与截图不入Git。提交前再次完整验证：小程序143项、后台81项、后端195项通过，后端7项独立MySQL/Redis环境未配置跳过；两前端check与后端Ruff/格式/mypy49模块通过。发布云端和上传体验版不属于本次推送操作。


2026-10-21后台卡片列表排序：根据用户截图要求，管理列表改为当前发布版本的发布时间倒序，未发布草稿使用创建时间，时间相同时按卡片ID倒序保持分页稳定；锚点定位采用相同排序，搜索、状态和导入批次筛选保留。小程序及手动目录排序逻辑未变。新增3项回归，修复前均因顺序断言失败，修复后排序测试5项通过；完整后端210通过、7项因真实MySQL/Redis依赖跳过，Ruff检查/格式和content_api.py的mypy通过。已仅重启受local_share管理的本地admin进程并确认ready，其他进程记录不变；浏览器访问开发后台停留在登录页，未执行登录后的视觉验收。没有提交、推送或发布测试/生产环境。仓库其他未提交的导入移除修改保留。

2026-10-21列表修复提交验证：用户要求提交远程test，本轮仅提交后台查询按钮与API最新发布时间排序。API按暂存树导出隔离快照，排除并保留工作区正在开发的导入移除功能；隔离完整回归198通过、7项MySQL/Redis环境跳过，排序回归5项均包含其中，Ruff检查/格式及mypy通过。后台重新验证81项、完整check通过，查询按钮点击/回车已在本地Chrome实测；截图留在本机不入Git。此次操作仅提交和推送，不执行云端部署。


2026-10-21导入判重与资料移除：按用户批准方案，排除已删除卡片的普通及历史导入映射，旧批次和重传可新建草稿；新增同批次ZIP及单卡的单个/批量移除、版本及归属校验、持久幂等与已接受保存保护，保留卡片/素材/历史。前端新增独立移除选择与确认、目标失效后新增入口、暂存缓存和迟到响应隔离；冲突修改可明确放弃，ZIP移除不误用卡片50项上限。最终后端211通过/9外部条件跳过，Ruff/格式/mypy49模块通过；前端93项与完整检查/构建通过；真实MySQL28项、Chrome6条流程通过。独立复核2项P2均经失败回归修复，无延期项。仅合成隔离验收数据，未提交、推送或部署；同期卡片排序改动由其任务独立交付并保留。详见docs/implementation/import-removal-progress.md。


## 2026-10-21 测试环境导入修复发布

按用户后续部署授权，管理API/worker/dispatcher部署 a5d5979，后台部署 b4c4f6d；保持结构0013，无数据库迁移。公网及三服务健康、前端产物哈希、受保护六容器身份均通过。真实测试域名四项验收通过，覆盖删除后重传、再次判重及重复项移除、并行ZIP上传中单个/批量移除、同包部分卡片移除后刷新保存、弹窗目标删除后保留编辑按新增。测试MySQL只读核对结果；7批次专用合成资料及5张草稿已按边界清理，未操作其他卡片。完整版本、首次发布回退和浏览器等待修正记录见 import-removal-progress.md 的测试环境部署与云端验收章节


## 2026-10-24 V1.5验收修复后端交付

按已批准计划完成问题1/2/3/6/8后端范围：整批导入软删除及原始updated_at版本/持久幂等/进行中保存保护/迟到解析、上传与发音拦截；新发布、新版本和重新上架置顶、跨管理员目录锁及冻结操作快照内校验；学习记录/日期明细/新records和day队列排除已删卡且成绩及打卡事实保留；反馈审核默认关闭的集中开关，开启恢复原严格规则。新增兼容迁移0017，管理员API和Worker相关门禁同步；权威管理OpenAPI已更新，小程序快照无差异。关键回归及迁移经历失败后修复；最终完整SQLite369通过/24外部条件跳过，专用真实MySQL8.4.13加Redis/Celery390通过/3 SQLite专属跳过；Ruff、184文件格式、mypy62源码、diff及两角色工厂契约比对通过。仅本仓本地实现和提交，未推送部署、迁移现有业务环境或清理真实数据。第3条隔离完整发布链路通过，云端当前仍下线的根因未凭此宣称解决；最终三端HTTP/Chrome联调由主协调收敛。详见docs/implementation/v15-acceptance-api-contract.md与docs/verification/v15-acceptance-api.md。

## 2026-10-24 release 部署与 RDS 迁移准备

按用户要求，juya-cli 生产分支门禁增加精确 release，保留 main、测试仅 test、干净工作区及实际分支/提交清单校验；CLI 58 项 Node、259 项引擎测试通过，10 项外部能力场景跳过。发现后端部署预检固定数据库主机 mysql，新增 JUYA_EXPECTED_DATABASE_HOST 显式配置，默认 mysql 兼容现有部署；保留环境库名、应用账号、Redis、OSS 和角色门禁。新增 16 项真实配置校验先出现 4 项预期失败，最小修改后全部通过；后端完整 385 通过、24 项外部条件跳过，Ruff 检查、185 文件格式检查、mypy 62 源文件通过。API CI 增加 release 触发，产物仍为两个角色的不可变镜像，不自动部署。

只读核查发现源生产库 29 表、版本 0010，业务表为空，仅迁移与系统初始化记录；生产 API/Worker/dispatcher 尚未启动，测试和共享 MySQL 正在运行。ECS 到 RDS 内网 DNS/TCP 通过，尚无账号登录、导入或切换验收。源端字段加密/查找密钥一致，迁移保留原值。完整控制台步骤、单库备份恢复、逐表核验、升级到 0017、切换及回退边界见 docs/operations/rds-production-migration.md。用户选择自行操作阿里云控制台；本轮未创建云账号、修改白名单、修改生产运行文件、迁移数据或切换流量。CLI SSH 密钥授权仍需部署前单独解决；本次已有密码诊断不能作为 CLI 发布登录已通过的证据。

## 2026-10-25 修订16学习授权本地交付

按用户批准计划合并整合04并实现统一学习授权、免费全局前N张、A02配置核对、A05筛选、A06四类操作与审计、小程序受限摘要及缓存回收，迁移0018默认未启用且不赠送旧用户授权。业务规则优先，保留最近验收修复；源码仍统一在juya-api，CLI逻辑目标不改名。最终SQLite395通过/26环境条件跳过，专用真实MySQL＋Redis418通过/3 SQLite专属跳过，后台169项、小程序322项通过；三端静态检查、后台/H5/微信测试构建、包体及契约一致性通过。独立审查5项Important均经失败回归修复，无延期项；本地合成数据真实HTTP/Chrome验收及七张截图完成。四仓均为test，三个业务仓库为未提交修改；未推送、部署、上传体验版，未修改现有业务数据。真机、云端、265态逐像素与生产资源拓扑另行验收；详见[完整交付与发布门禁](../verification/revision16-learning-access.md)、[验收追踪](revision16-acceptance.md)、[设计映射](revision16-design-map.md)。

## 2026-10-25 测试环境免费场景与授权验收

按用户“继续验收，发现问题直接修复”授权，使用专用测试账号通过公网管理/小程序接口验收免费集合、N边界、开通/续期/自定义/撤销、过期数据回收、旧音频与点词发音GET/HEAD/Range、收藏完成幂等、队列、筛选与审计，62项断言通过。后台浏览器实际保存开通、续期、撤销并核对12条用户审计；已打开的微信模拟器直连测试API验证免费/受限标识、提示、完整音频进度、预设词发音和译文。补充跨10条后台分页、排序使旧确认失效、跨年和闰日4个用例，独立juya_verify真实MySQL专项32通过；后台169、小程序334回归通过，修改测试Ruff及diff检查通过。未发现可复现业务缺陷，无业务代码修改或重新发布。微信基础库出现一次routeDone系统错误，后续导航成功，根因及体验版真机保留待核实。

原免费配置未启用；临时测试后恢复enabled=false/N空，修订号5和schema_contract2单调保留，恢复操作入审计。专用授权撤销、会话关闭且公网401，测试账号及自身学习事实/审计保留供复查。既有9类业务数据摘要一致，模拟器只正常产生既有账号的阅读状态/进度，未改其成绩；两接口ready、无活动任务。未操作生产环境。体验版真机全过程、真实跨午夜、弱网及离线缓存未折算通过。详见[本轮验收报告](../verification/revision16-test-acceptance-20261025.md)。

提交前按用户指定目标，在独立test工作目录复核：完整SQLite回归399通过/26环境条件跳过，真实MySQL授权专项32通过，两个修改测试文件Ruff及格式检查通过。提交范围仅为本轮边界测试、验收报告和执行记录，不混入release分支的生产部署记录。

## 2026-10-25 修订16测试发布

用户新增发布授权后，三仓提交并推送test；API650c022、后台1e86b6e已通过既有发布引擎更新测试环境，小程序9889b78官方CLI上传版本1.5.0-test.1025.1成功。CI真实MySQL/Redis418通过/3 SQLite专属跳过。测试库先备份再迁移0018；六服务健康、零重启和OOM，受保护5容器及业务表行数不变；公网角色隔离、契约、登录/授权筛选/免费配置读取和后台安装/公网字节核验通过。浏览器站点安全策略阻止mp.weixin.qq.com，设为体验版待用户操作；首次启用门禁保持关闭，N未配置、不赠授权。未审核或正式发布小程序，生产未发布。详见[发布记录](../verification/revision16-test-release-20261025.md)。

2026-10-25体验版确认后收尾：用户明确确认1.5.0-test.1025.1已设为体验版。将测试管理API的首次启用就绪开关打开，保留私密原配置，仅重建admin-api、固定原镜像，其余10容器身份/状态不变。两公网ready、契约/角色隔离、实际管理员登录及配置读取复核通过；数据库0018/contract1，免费规则未启用、N未配置、权限三表仍空，不新增授权。协调发布完成，后续管理员自行核对免费名单后保存N；平台体验版状态依据用户确认，非工具独立观测。

## 2026-10-25 生产数据库 RDS 迁移与连接切换

按用户明确授权从本机账号文件读取凭证，将源生产0010的29张表导入空RDS生产库；导入后的结构、逐表行数和内容摘要一致。使用release 4ba194f对应的CI管理镜像执行显式升级0018，目标42表结构与已验证0018一致，原有记录保留、新增表为空。仅修改生产admin/mini/migration运行文件的数据库URL和预期主机，三份实际配置连接验证及管理角色运行预检通过，其余配置和密钥保留。11个既有容器、7份测试配置、测试库结构/行数/内容摘要完全不变，两测试API公网ready。源0010库、原配置及两端逻辑备份保留，本机备份摘要复核通过。生产服务原本未启动，本轮未启动API/Worker/dispatcher、未初始化管理员或发布前端/小程序；后续正式应用发布另行执行。详见[实际执行记录](../verification/rds-production-migration-20261025.md)。

## 2026-10-25 生产服务首次发布与管理员初始化

按用户授权发布 release 后端双角色及后台网页，生产六个 API/Worker/dispatcher 容器均 healthy、零重启和 OOM，全部连接 RDS 生产库 `0018`。新增首位管理员 `admin`，密码只在本地私密账号文件，生产 API 实际登录、会话 Cookie 与 CSRF 校验通过。后台网页和两 API 公网就绪及角色隔离通过。初次管理 API 公网检查因生产 HTTPS 配置未安装而失败；使用现有证书安装正式 vhost 后复验通过，首次无上一版本的自动回退异常需另行修正。测试原有 11 容器、7 配置和数据库结构、行数、内容摘要与部署前一致。未发布微信正式版，也未启用学习授权开关。版本和证据详见[生产发布记录](../verification/production-service-deployment-20261025.md)。

## 2026-10-26 后台登录会话延长至30天

按用户要求，将管理员会话默认时长由12小时调整为720小时（固定30天）；原有登录流程已共用该配置设置服务端到期时间和浏览器Cookie的Max-Age，无需修改鉴权或前端逻辑。同步运行配置示例和README。已有会话保留原到期时间，新版本上线后重新登录获得30天有效期；主动退出与CSRF校验继续生效。本地未发现管理员时长环境变量覆盖，未读取或修改云端配置。

新增Cookie持久有效期、数据库会话到期时间、登录13小时后、第30天前一秒及第30天边界回归，旧实现出现3项预期失败，修改后登录测试14项通过。首次完整回归因终端PATH未包含项目已有FFmpeg而出现素材处理相关失败，加入本机`.tools/ffmpeg/bin`后重新完整验证415通过、26项真实MySQL/Redis环境依赖测试跳过；Ruff检查、205文件格式检查及mypy66源码文件通过。测试使用隔离SQLite，不连接现有业务数据库。本轮仅本地修改，未提交、推送或部署，无数据库迁移。

## 2026-10-26 重叠高亮与固定用户编号本地交付

用户要求先单独提交登录时效，已完成本地release提交1a8e141。随后按批准计划放开有效高亮区间重叠，后台与小程序完整渲染覆盖范围、保留完整单词查词引用；新增0019迁移及事务编号分配，已有用户按注册时间/UUID升序补号，新用户递增，后台各处统一显示Juya001且保留原反馈编号与UUID关联。搜索、契约、服务就绪、需求真源及未来迁移顺序同步。独立审查发现并修复旧反馈回执重试缺user_code的兼容问题，六种回归先红后绿，保存回执与消息数量不变。

最终SQLite432通过/28外部依赖跳过，专用真实MySQL8.4.13与独立Redis/Celery457通过/3 SQLite专属跳过，后台174项、小程序340项通过；三端静态检查、后台/H5/微信测试构建及主包余量检查通过。真实Chrome/隔离HTTP完成重叠预览发布、用户编号搜索/详情UUID导航及反馈编号一致性验收，截图已核对。新功能在三个原检出留待检查，未提交、推送、部署或迁移真实业务库；详见[验证记录](../verification/overlap-user-codes-20261026.md)及[迁移顺序](../operations/user-number-migration.md)。


## 2026-10-28 修订17主题听读本地增量交付

- 当前真源为仓库根AGENTS链接的当前开发版（修订17增补02、CHG-0027、T01—T276），首页/学习记录/账号三Tab及场景/听读双模块已替代旧两Tab规则。
- 新增独立听读分类/主题/文章草稿和发布版本、两套排序、M确认、统一授权、双类收藏完成/共享打卡、版本进度、受控媒体/查词、DOCX/ZIP独立导入与删除恢复，以及独立持久时间轴任务/worker和腾讯适配。
- 增量迁移0020只新增13张表；0021隔离未发布主题改动；0022增加分类英文名称和主题简介。旧请求省略新字段不清空。原场景/授权/分享/反馈数据保留，未推送、部署或自动提交。
- 父任务备份后仅迁移本地juya_local到0022，自动化仅使用隔离juya_verify；对本地业务库执行alembic check通过。ready最低0022，旧库不假ready。
- OpenAPI已导出，实际接口契约及完整需求/验证追踪见[修订17后端契约](../handoff/revision17/source/开发方案/修订17-后端契约.md)和[后端实施报告](../handoff/revision17/source/开发方案/修订17-后端实施报告.md)。
- ruff、mypy75源文件、diff空白检查通过；最终完整SQLite及匹配MySQL结果由实施报告记录。既有Windows的fcntl/POSIX模式/proc及ZIP造包差异不伪装通过。
- 真实腾讯ASR返回AuthFailure.UnauthorizedOperation，未开通成功；本地任务未配置时真实失败并降级，不能把替身或本地构建当作真实ASR/微信真机验收。

修订17恢复后收尾：R1—R7已修复并经独立复审；OpenAPI导出显式UTF-8/LF，三方契约一致。最终原始需求复核补齐38.3/38.6批次更新已有文章S1，候选绑定目标版本、差异确认后更新原草稿，原发布版/历史不变；同内容和媒体不同上传ID语义跳过，精确媒体授权，无新增迁移。S1后全部听读与OpenAPI50通过/4项MySQL限定跳过，真实本地MySQL补项10项及语义边界1项分批通过；S1前完整SQLite460通过/31跳过/15既有Windows失败，不累加或称完整MySQL通过。最终交付及未验事项见[本地交付说明](../handoff/revision17/source/开发方案/修订17-本地交付说明.md)。仍仅本地0022，未提交、推送或部署。

## 2026-10-28 MacBook接续提交

用户新增明确授权把当前三端代码提交推送远程test，用另一台MacBook继续；CLI本轮无改动，仍不授权部署或远程迁移。Mac已有四项目环境，保留原配置和本地数据，备份后只做增量迁移；完整需求由用户自行同步，版本/hash引用以及报告、追踪和9张截图已归档到docs/handoff/revision17，根HANDOFF.md给出Mac本地初始化/启动及待办；不依赖Windows父目录或私密runner。提交前新鲜SQLite471通过/32跳过/15既有Windows失败，失败标识与前轮完全相同；后台完整188、小程序383通过，检查/构建通过。详细计数和边界见[提交前验证](../handoff/revision17/pre-push-verification.md)。

## 2026-10-28 修订17还原度修复：主题英文名、用户发布预览与统计

本域按修复计划Task3及A-05—A-08实施，仓库保留原test分支，未提交或推送。0023只兼容新增`listening_topics.name_en VARCHAR(300) NOT NULL DEFAULT ''`；输入省略/None不清空已有英文名，输出为空串兼容旧行，中文名和简介保持。两角色ready最低迁移同步为0023。迁移测试在临时SQLite验证旧表和中文简介保留，并检查MySQL离线DDL仅新增列；本域没有在业务库上运行迁移，实际本地备份和0023升级由父任务单独记录。

管理员新增`GET /api/admin/v1/listening/articles/{id}/published`，复用Article形状，仅读取当前有效ListeningVersion.payload，并使用发布主题/顺序、发布正文的词数与时间轴，草稿元数据为空；独立`published/media/{media_id}` GET/HEAD只放行当前发布快照引用的受控媒体。无发布版、下线/删除、跨文章/新草稿素材均不开放；不调用学习者会话和学习写操作。用户已学听读与打卡来源均改为`/listening/:id/published-preview`，页面只读复用ListeningPreviewPanel，媒体走发布专用前缀。

A14列表恢复场景/听读独立列、紧凑搜索/三类筛选、刷新及共用授权说明；A15恢复2×2指标、资料分隔行和值右对齐、独立授权审计表（管理员、动作、前后状态）、学习记录分卡与共同授权文案；A16统计为36px数字及191px紧凑卡，口径说明使用白底圆角描边容器。设计实现依据A14/A15/A16高保真上下文及对应PNG；浏览器视觉与真实已有历史联动由父任务继续验收。

为设计中的真实数据展示，Summary兼容增加`audio_duration_seconds`和可空`progress`、`reading_paragraph`；继续卡只读取本人当前发布版本进度，换版后进度重置且无旧段落号。段落按原始codepoint与非空CRLF/CR/LF行定位，缺保存进度返回null。场景PersonalSummary增加`favorited_at`，只使用现有Favorite.created_at。两角色OpenAPI及两前端JSON/生成TS均通过既有脚本重新生成并格式化。

最终新鲜验证：API `ruff check .`通过、`ruff format --check .`248文件通过、`mypy src`75源文件通过、完整`pytest -q` **493通过/32项真实MySQL或Redis环境依赖跳过**（119.29秒）。完整命令PATH包含本机已有`.tools/ffmpeg/bin`；自动化均为临时SQLite。新增HTTP测试验证发布/草稿差异、换版和跨文章媒体隔离、角色凭证隔离、无用户学习写入、不可用状态、英文名往返、继续进度和CRLF/emoji段落偏移。后台完整测试**200通过**，最终整库`pnpm check`及`pnpm build`通过；jsdom仍输出既有HTMLMediaElement.pause未实现提示。未连接真实MySQL/Redis做本轮并发验证，未启动服务、控制浏览器或操作远程。

## 2026-10-29 提交远程test前复核

用户明确要求将本轮代码提交到远程test。小程序提交014e95a、后台提交22c3a6e，CLI无改动；配套清单repository-set.json已更新。前端完整检查及测试环境构建通过，小程序398项/后台207项通过；API Ruff、格式248文件、mypy75源文件通过，完整pytest493通过/32真实MySQL或Redis环境依赖跳过（120.27秒）。两前端与API OpenAPI JSON语义一致。

本轮只提交和推送源码，不部署、上传体验版或迁移远程数据库。新代码最低schema为0023；本机业务SQLite已先备份再增量升级，另一台机器须核验并备份其已有本地数据库后迁移。开发者工具此前停留在类型解析失败后的旧开发产物，重新启动本地watch后已现场确认M03分类胶囊/选中底色/主题分隔行，并验证源码不变时再次热编译成功。iPhone/Android真机、真实ASR和MySQL/Redis并发仍未验；导入进度保持明确的合并请求进度，不冒充各包独立传输进度。

## 2026-10-30 整合05／修订17本地执行

需求更新至T01—T300/R01—R19；55当前画板、103关联状态、35旧问题重评与42实现截图见`docs/handoff/revision17/integration05/README.md`。三端在隔离工作树codex/revision17-integration05，原业务目录/配置/数据不覆盖，无push/部署/远程迁移/OSS上传。最低schema仍0023。

完成目录引用安全删除/原子排序、主题英文必填、直接M保存、模板/归属识别、双出口导入与直接发布/回执、历史口径、六外置背景/语块色/收藏反馈等。API513通过33跳过；仅juya_verify的守卫MySQL专项37通过；后台220/54及真实本地HTTP浏览器2通过；小程序407/89、check/H5/mp构建及主包预算通过。一次独立审查发现未知提交遇明确409仍锁定的问题，已RED→GREEN修复并完整回归，无延期Minor。

R06合成同账号时间/免费集合/资源请求和R13真实本地任务输入版本已分别留证。未识别原反馈账号；002/003缺原件；真实ASR/TTS/OSS、微信身份/设备及全量55+103逐图设备验收仍待，未计为通过。新SHA及配套commit见当前handoff；旧冻结报告保留。

## 2026-10-30 对话时间轴修复

用户确认小节标题/角色标签保留显示而不参与朗读高亮。新增六个边界回归，实际对话仍100%匹配；保持原始字符偏移、正文和音频。测试环境ASR凭据漏配已修复，两篇散文已ready；生日聚会的218个实际朗读词仍待新规则发布后恢复。发布和验收结果另行记录，未将待完成项标为完成。规则见docs/superpowers/specs/2026-10-30-listening-dialogue-timeline-design.md。


## 2026-10-31 听读删除后重新导入误判重复

修复听读导入 `classify` 将软删除文章及其历史已保存候选继续纳入判重的问题：文章来源仅匹配 `deleted_at IS NULL`，候选来源仅匹配未移除、未保存的有效暂存项。正常存在的文章及未保存候选继续防重复，不删除历史文章、媒体或学习记录，无数据库迁移。

读取本人批次详情时，在现有 catalog→batch 锁顺序和写事务内复核重复候选；来源失效后恢复正常候选并建立时间轴任务，变化时递增批次 revision、回到 review，使旧核对回执失效。重复读取保持 revision 稳定，不将历史已保存候选重新变成待保存项。

两条参数化真实 HTTP/SQL 回归先复现失败，再验证删除后重传、已跳过批次刷新恢复、时间轴任务、再次读取稳定性、新草稿保存及正常判重。最终专项 `tests/test_listening_imports.py tests/test_listening_import_updates.py` 为 **17通过/1项专用MySQL跳过**；最终完整 `pytest -q` 为 **521通过/33项MySQL或Redis环境依赖跳过**（125.42秒）。测试 PATH 使用本机已有 `.tools/ffmpeg/bin`，数据库仅为临时 SQLite；Ruff检查、260文件格式检查、mypy77源文件及diff空白检查通过。独立代码复查无阻断问题；本轮未验证真实MySQL并发，未提交、推送或部署测试环境。

用户随后明确本次只将修复提交、推送到远程 `test`，留待下一次其他需求一起发布；本轮不部署测试环境。

## 2026-11-02 正文单词近秒播增量实现

按用户批准方案完成场景发布后异步预生成、小程序全文预下载与跨弹窗缓存，沿用受控引用、实际读音共享缓存、短期票据、逐次播放验权及原有音轨互斥。预热受持久派发闸门限制，用户点击可优先处理；发布回滚、同版重新上架、配置失效、预算冷却和运行期间下线均有覆盖。补热命令默认仅预览，执行限定显式本地发布卡片，不新增HTTP契约或迁移。

API完整SQLite555通过/43环境依赖跳过，最后超长词元隔离补丁经预热/词典/发音/jobs专项43通过/5专用MySQL跳过；根代理独立在身份核验的juya_verify运行新增预热16项全部通过，补热恢复另行复验通过。API Ruff/格式/mypy通过。小程序Node22.23.3下95文件445测试通过，四项check、H5及微信构建、页面/主入口/包体检查通过。独立代码审查无剩余P1/P2。

详细范围、命令及验证限制见[验证记录](../verification/word-audio-instant-20261102.md)。本轮未提交、推送、部署、上传体验版，未执行业务场景补热或真实云调用；iPhone/Android实际出声和准备完成后P95≤500ms仍待真机验收，未将自动化通过当作手机秒播证明。


用户随后授权将所有应用服务部署测试并上传小程序；现已完成。API固定c690358、后台336d5b2、小程序3d12752；7服务healthy、双公网ready及源码哈希核验通过，微信1.5.0-r17.06.1102.3官方上传成功，体验版未切换。CI真实MySQL/Redis596通过/3跳过，schema仍0024/contract3、无迁移、生产容器保持。详见docs/verification/word-audio-test-release-20261102.md。


## 2026-11-02 生产应用发布

- 用户授权test合并release与生产部署，生产双API/各自Worker及dispatcher/独立听读Worker共7服务健康，后台公网文件哈希一致，CLI修复已部署
- 生产备份恢复核验及0018→0024/contract3迁移完成，原业务记录保留；微信生产包1.5.0-prod.1102.1上传，体验版未切换
- 固定公开素材改用生产API域名，11文件公网200且哈希一致；生产OSS读写验收仍因凭据权限被拒绝，待用户补齐，不标为完成
- 证据：[生产发布与剩余前提](../verification/production-release-20261102.md)及同名JSON


## 2026-11-03 生产OSS授权复验

- 用户确认授权后，juya桶Put/Get与11项私有静态资源上传读回哈希通过，删除探测仍被桶策略拒绝，不标为通过
- 修正生产不可达OSS内网端点，按原流程重载7服务；实际双API ObjectStorage读写、公网登录及接口通过，测试/基础设施身份保留
- 微信包仍为1.5.0-prod.1102.1，11项生产域名素材200及哈希一致，无需重打包，体验版未切换
- 证据：[生产OSS复验](../verification/production-oss-verification-20261103.md)及同名JSON


## 2026-11-03 单历史版本保留与服务器清理

用户授权测试/生产各只保留1个历史版。已清理旧发布/重复归档/无引用镜像，保留当前及previous完整发布；49份备份SHA-256不变，19容器状态不变，14应用healthy及7个公网入口/健康检查通过。根盘可用约12GiB、使用69%。CLI保留规则同步test/release并部署工作台；数据库仍0024/contract3，未回滚/迁移。详见[记录](../verification/release-retention-20261103.md)。

## 2026-11-03 原句自动对应、免费优先与下一篇修复（test）

按用户要求，API、后台、小程序原目录均切换到`test`开发；切换时各仓`test`与`release`同头且工作区干净。开发验证阶段未提交、推送、部署、上传体验版、迁移数据库或改写真实业务数据。用户随后明确要求将三仓改动提交并推送到远程`test`，本次不部署。

- 听读词汇导入、保存和发布自动匹配文档原句及常见词形，取消人工确认门槛，兼容旧草稿和旧批次。预览校验副本，不改正文或指纹；发布先校验原令牌再保存真实来源，同步当前判重标识并保留原导入身份。重复句可手选位置，未知变形可补选，不能准确对应时保留原句提示、不伪造偏移。旧批次读取时重核原句审核错误，实际变化才递增版本，其他资料缺失仍阻止发布。
- 后台场景排序入口可从任意筛选直接打开完整已发布集合，退出保留筛选。手机端场景及听读列表均在分页前免费优先，组内沿用人工顺序；场景来源快照、听读分类队列同步展示顺序，既有快照保留固定顺序，收藏/记录顺序不变。
- 微信页面加载时还原一次URL编码的队列凭证，避免重复编码导致解密失败。下一篇继续逐篇复核权限、跳过未授权文章，保留分类末尾、复习及跨账号凭证拒绝。

各回归先复现失败再修复。提交前最终完整临时SQLite为**571通过/43项MySQL或Redis环境依赖跳过**（147.83秒）；最终导入、下一篇和免费排序相关六文件专项为**57通过/1项专用MySQL跳过**。Ruff、286文件格式检查、mypy81源文件通过。后台最终58文件**263测试通过**，小程序95文件**450测试通过**；两端`pnpm check`、后台构建、小程序H5与微信测试模式构建、18页配置/共享音频入口/主包预算检查通过。独立审查发现的问题已修复并复验，最后旧批次读取补丁定向复核通过。配套后台`4f46cc6`、小程序`2a68a7e`已推送远程`test`，本地与远程提交核对一致，工作区干净。

本轮为本地源码、HTTP/SQL及组件验证；临时SQLite和测试替身不代表真实MySQL/Redis、真实云及微信真机验收。

## 2026-11-03 列表读取与听读缩略图本地性能优化

按已批准的跨端性能方案，仅修改本地API源码与隔离测试。听读分类文章、旧主题兼容文章、收藏、记录和日学习文章摘要批量读取发布版本、媒体、分类及当前用户完成/收藏/今日完成集合，保留分页前筛选和既有排序。共享授权及目录版本采用当前操作内的显式快照，不跨请求或账号缓存。场景列表复用同次请求授权/目录版本与已查卡片。听读首页分类总数、本人完成数和受限数改用数据库分组；首个有效发布缩图由窗口查询选择，继续学习按批量历史、同分类队列和本人完成集合选择，保留原授权和后继顺序语义。

听读直链缩略图与thumbnail用途票据统一使用现有有界ListThumbnails缓存和144×216内、WebP quality60的小图配置；每次读取仍先校验登录或短票据对应会话、当前发布版本及素材归属，再读取缓存。原图不改写，普通受控原图仍需要学习授权，Range/HEAD长度来自实际返回小图字节；无新增路由、公共响应字段、表结构或迁移。

新增`tests/test_catalog_performance.py`十项真实HTTP/SQLite回归。SQL-count及缩图大小回归先见红再修复：听读文章/收藏/记录1→12项原为12→100次SELECT，优化后分别12→12、13→13、13→13；首页空→12篇由24→132优化为21→21；场景1→10项由20→38优化为19→19；含1→12条继续学习历史由53→186优化为23→23。另覆盖跨用户个人状态隔离、授权撤销/跨日到期实时生效、草稿/下线/删除/缺发布版本与删除分类过滤、真实小图尺寸/字节上限、缓存复用、Range/HEAD实际长度、下线后缓存拒绝及原图保留。

最终完整临时SQLite测试为**581通过/43项MySQL或Redis环境依赖跳过**（158.09秒）；新增性能回归单独**10通过**；听读/下一篇/授权边界/媒体组合专项**72通过**（含新增文件早期7项，不能与完整结果相加）。`ruff check .`、287文件`ruff format --check .`、`mypy src`81源文件和`git diff --check`通过。两条分类SQL额外通过MySQL方言编译检查，未连接数据库。独立只读复查未发现确定P1/P2。

本轮未提交、推送、部署、远程迁移或读取/写入真实业务库；生产现状保持。SQL次数证据来自隔离SQLite，并不代表真实MySQL执行计划、真实云存储耗时或微信设备端性能；这些验收仍待后续明确授权与实际环境验证。


## 2026-11-04 列表性能测试 mini API 发布（11-03 批次）

用户按计划执行授权后，本轮mini三服务于北京时间2026-11-04 00:05:34（UTC11-03 16:05:34）通过既有原生CLI发布固定源码`00a4c11`。先将quality时限20→30分钟，保留真MySQL/Redis完整门禁；再补齐父提交e6b393b遗留的四处OpenAPI description并前置契约检查，无路径/参数/响应/schema变化。最终官方CI契约、质量、双角色镜像全绿，真实MySQL/Redis**621通过/3跳过**（1140.18秒），仅下载并发布mini官方产物。

原生bundle/镜像/source/环境/词典/健康闸门与失败恢复保持，公网ready200、匿名听读列表401、mini域名admin auth路径404，三容器healthy且重启0；原生finalize保留当前00a4c11及上一版c690。schema前后0024/contract3无迁移，测试其余四应用服务、生产及其他16容器完整元数据不变，无ACL或业务资料变更。真实学习身份首屏及音频端到端真机延迟仍待验。详细身份、实际时间、保留版本及无秘密前后快照见[发布记录](../verification/loading-performance-test-release-20261103.md)，三轮CI证据另见[CI回执](../verification/listening-performance-test-ci-20261103.json)。


## 2026-11-04 生产发布与微信1.0.0

用户授权四仓test合并release并发布生产。双API及7个生产服务、管理后台已部署，CLI线上与release一致；数据库保持0024/contract3、无迁移，测试/基础设施12容器未变。微信生产包1.0.0/100已构建及官方CLI上传，体验版由用户切换。后台实际Chrome登录及用户/统计/反馈/听读页面真实API200、无JS错误；生产静态压缩资源、公网与文件哈希通过。自动化结果、CI不可变镜像、保留版本、完整证据及真机未验边界见[发布记录](../verification/production-release-20261104.md)和[回执](../verification/production-release-20261104.json)。

## 2026-11-04 数据库中文用途注释（实施中）

- 已补齐55张业务表389个字段及Alembic版本表说明；0025冻结56表390字段注释，保持最低schema0024/code contract3。
- 真实本地MySQL专项18通过，覆盖建库、带数据升级、部分DDL重试、在线算法和5秒锁等待超时；Ruff/格式/mypy通过。全量回归及官方CI仍在执行，远程尚未迁移。
- 本地整合06SQLite已备份后升级0025，业务行数保持；SQLite只保存模型说明，不支持物理COMMENT。旧ui.sqlite为0023，未执行涉及业务变换的0024迁移。
# 2026-11-04 双端中文接口文档

- 按用户要求将管理端与小程序端的 OpenAPI 分组、操作摘要/说明、字段标题/说明、参数与响应状态说明统一为中文；保留路径、字段名、operationId、枚举及验证约束。补充 307 个字段、198 个模型标题、199 个操作、26 个分组及 99 个上下文覆盖。
- 测试文档入口见 README；Nginx 仅开放测试角色的精确文档路径，生产配置渲染逐字节不变。
- 本地 Ruff、格式、mypy 通过；全量 SQLite 回归 590 通过/45 条件跳过，最终文档和契约专项 17 通过。初次媒体专项因隔离进程未加入本机 FFmpeg 路径失败，补齐现有工具路径后通过，未修改媒体业务实现。
- 官方 CI 41848215340 全部成功，真实 MySQL/Redis 632 通过/3 条件跳过；源码 `0698e765f28ec8f1f86ab3b2d55a6b4ed2b39926` 已通过原生发布器更新测试双 API 六服务。公网完整契约与源码导出相等，全部操作与字段说明为中文；其余 13 个容器和全部 Nginx 配置不变，数据库保持 0024，生产未发布。浏览器工具超时，未完成渲染验收。详见 `docs/verification/chinese-api-docs-test-20261104.md`。


## 2026-11-04 数据库中文用途注释在线同步完成

- 固定a9e271b，官方CI41848737797真实MySQL/Redis626通过/3跳过，双角色镜像通过；本地固定源码全量同为626/3。
- 测试及生产均完成0025/contract3，56表390字段中文注释精确一致，非注释结构和19个既有容器、当前/上一应用版本指针不变，四公网ready200；一致性备份已完成并复算SHA。
- 本地整合06SQLite备份后升级0025；SQLite说明保存在模型，旧ui.sqlite0023保留。无应用发布或重启，完整回执见docs/verification/database-comments-20261104.md及JSON。

# 2026-11-04 Swagger 公共状态码与成功响应展示

- 按用户要求将公共状态码及统一错误返回格式集中到文档顶部，每个操作仅展示 2xx 成功响应；页面读取实时 OpenAPI 后创建展示副本，原始契约、错误处理和鉴权不变。
- 本地 FastAPI 与测试 Nginx 共用 swagger_docs.py 生成页面；静态页面可独立发布，避免仅更新文档时替换业务容器。生产文档保持关闭。
- 本地 Ruff、格式、mypy、契约导出零差异通过；页面 JavaScript 实际执行专项和契约专项 12 通过，全量 SQLite 回归 595 通过/45 条件跳过。独立审阅无未解决 P1/P2。
- 源码 d47dd21 已推送 test，测试两页已独立发布。公网实际页面脚本验证管理端 124、小程序 75 个操作均仅展示成功响应、公共说明只出现一次；Chrome 实际展开截图中的发音接口确认 Responses 仅列 200。两份原始规范字节不变，全部 19 容器和其他 Nginx 配置不变，数据库保持当前实际基线 0025。未迁移、未替换业务镜像、未发布生产；详见 `docs/verification/shared-api-status-docs-20261104.md`。

## 2026-11-05 部分匹配高亮

按用户要求实现匹配词高亮/遗漏词跳过及已有任务复用（源码待发布）；生产仅《银行》复用原结果恢复ready/118词，无新ASR提交。详见 `docs/verification/listening-partial-highlighting-20261105.md`。

## 2026-11-06 整合07学习笔记后端（Task 1）

- 已在用户指定的test分支实现独立PDF笔记版本、草稿有效/待处理附件与保留/设置/移除/未决决策、0026增量迁移、实际PDF异步校验、候选/发布预览、独立版本下载票据、SQL笔记筛选与learning_notes来源队列。最低schema0026，code contract3；API与worker健康探针统一要求新schema。
- ZIP按包实例与完整目录隔离，旧包省略PDF保留目标；去重含当前/有效回退PDF字节摘要及动作，等价正文复用原行/媒体/正文版本。PDF-only发布保持原排序、阅读位置、音频和学习事实，不生成TTS；笔记变更推进目录版本。
- 真实MySQL列表使用同一读取快照保证total、有效页、行与has_study_note一致。资源GET/HEAD/Range仍逐次复验当前会话、卡片、免费/授权及独立笔记版本，不写学习数据。详细接入见 `study-notes-contract.md` 与已导出的两份OpenAPI。
- 经两轮独立定向审查修复四项Important（ZIP正文漂移、内部keep、有效/待处理传递及分页快照）及同一项回退PDF重存去重；复审均通过。先RED后GREEN的专项日志保存在私有`.private/study-notes-fix-round*.log`；SQLite导入专项83通过/4条件跳过，MySQL专项33通过。
- 最终完整SQLite：638通过/49条件跳过，204.99秒；48项需真实MySQL、1项需隔离Redis。ruff check、ruff format --check和mypy src通过。最终完整MySQL：683通过/4条件跳过，434.23秒；跳过隔离Redis集成1项和SQLite专属回归3项。完整日志分别为`.private/study-notes-sqlite.log`和`.private/study-notes-mysql-full.log`，均exit0。
- 本Task仅本地隔离测试和源码提交；未推送、部署、业务库迁移、OSS/微信上传。真实微信文档预览、iOS/Android、真实云资源及前端交互待后续验收。其他历史授权与发布记录不扩大本Task范围。
- 最后补验原隔离Redis条件项：使用现有redis-server binary新建127.0.0.1临时端口/目录、空DB15，真实Celery独立子进程定向验证`test_committed_upload_survives_missing_dispatch_and_duplicate_broker_delivery`，1通过（2.17秒，exit0）。自己的Redis进程和临时目录已清理；未连接既有/远程broker，未变更功能。原完整套件计数不变。私有证据`.private/study-notes-redis-verification.md`及`study-notes-redis-integration.log`。

## 2026-11-06 学习笔记原子保留契约补足（Task1b）

- 针对Task2跨保存复审暴露的已批准能力缺口，新增可选`StudyNoteChange.previous_media_id`：仅set/unresolved接受明确有效ID，服务端验证ready PDF与管理员归属，一次保存未落盘有效B和待处理C；省略沿用原逻辑，null及keep/remove携带拒绝。重开/取消保留B，发布A与正文/排序保持。
- ZIP按最终目标与完整保留状态重验（包含省略note、keep、清空/切换目标），worker保存或判重前复验；合法目标历史附件例外不跨目标继承。无ImportFile不再自动视为手动上传，须有AdminMediaSource证明；删除源ZIP后不能借遗留Media串配。合法同目录、既有目标和真实单独上传正例均通过。
- PDF错误区分非PDF、结构损坏、无法解密、空与超限；包含PdfReader构造阶段的证书加密不支持。媒体/导入文件/candidate/单一失败候选issues复用实际安全原因，不回传底层异常。契约及OpenAPI已导出，无新route、reader、依赖或数据库迁移，仍schema0026/contract3。
- 独立定向审查原3项Important、1项Minor全部ADDRESSED，独立13项通过；修复先RED9失败/1通过，再同组GREEN10通过。受影响SQLite140通过/6条件跳过、真实MySQL67通过。
- 冻结后一次最终完整SQLite675通过/49条件跳过（222.70秒），完整真实MySQL720通过/4条件跳过（462.22秒），均exit0。SQLite跳过48项MySQL条件及1项Redis；MySQL跳过1项Redis及3项SQLite专属。队列传输未改，沿用Task1已完成的独立Redis/Celery补验，未重复运行。日志`.private/study-notes-task1b-full-{sqlite,mysql}.log`。
- ruff check、315文件格式检查、86源文件mypy及diff-check通过；报告`.superpowers/sdd/2026-11-06-study-notes/task-1b-report.md`。本Task仅本地源码与隔离测试，未改前端、业务库、远程环境或推送；真实UI由Task2验收，微信真机/云验证仍留待后续。

## 2026-11-06 笔记来源正文原子准入（Task1c）

- 对应Task3队列候选到详情之间PDF失效竞态，原详情GET新增可选`require_study_note=false`。true时按用户→目录共享→Card/PDF媒体共享的既有锁序持有至提交，复用published_note谓词并在锁等待后重验权限/时间；笔记移除/不可用返回409 study_note_unavailable，无新增ReadingStart。
- 合法notes正文仍按mark_started默认true写原本人＋卡片唯一开始记录，不新增PDF开始事件；mark_started=false仅资格探测/刷新不写学习事实。默认false、普通learning无PDF、正文版本检查、成绩与打卡语义完整保留。无新表/route/依赖/迁移，admin接口不改。
- 先真实HTTP RED4项，再真实MySQL四同步点RED；修复后分别11通过/4条件跳过及4通过。扩展SQLite专项123通过/7条件跳过，MySQL专项47通过；独立定向审查11项SQLite通过并核对4个MySQL同步点，未发现阻断。
- 冻结后一次完整SQLite：686通过/53条件跳过（230.20秒），完整真实MySQL：735通过/4条件跳过（484.20秒），均exit0。SQLite跳过52项MySQL条件及1项Redis；MySQL跳过1项Redis及3项SQLite专属，队列传输未改，沿用此前独立Redis补验。日志`.private/study-notes-task1c-full-{sqlite,mysql}.log`。
- ruff check、316文件格式、86源文件mypy及diff-check通过。契约第3/4节、mini OpenAPI及中文query已更新；报告`.superpowers/sdd/2026-11-06-study-notes/task-1c-report.md`。仅本地API源码/隔离测试，未改前端、业务库、远程环境或推送；小程序实际推进/跳过与真机验证交Task3/后续验收。

## 2026-11-06 整合07最终整体审查修复

后续发布状态：用户已授权推送test、部署测试并上传微信开发版。北京时间22:31:12完成，API f219a39／后台97937db／小程序d99a12c；官方CI738通过／3跳过、双镜像通过。测试库备份后0025→0026／contract3，55原业务表原字段及行数保留，7服务健康、12非目标容器未变。微信1.5.0-test.20261106.184331已上传，体验版用户自行切换，未部署生产。完整发布及后验见`docs/verification/study-notes-test-release-20261106.md`和同名JSON，下列为开发阶段记录。

- 学习笔记 PDF 的 GET、HEAD 和 Range 兑现请求须携带签发票据的 Bearer 会话。与票据不匹配的会话或匿名请求返回 401，签发会话继续重验当前版本与授权。图片和音频继续支持原生票据读取。
- ZIP 核对和保存共用目标草稿的笔记决策计算，核对显示有效附件、失败待处理件与原因。选择候选仅限当前包／目录，切换或清除目标重新计算；保留省略动作的落盘及去重语义。
- 完整临时 SQLite 688 通过/53 条件跳过（245.43 秒），本机 Unix socket 独立 MySQL 库 juya_verify 737 通过/4 条件跳过（487.91 秒）。SQLite 的 52 项 MySQL 条件及 MySQL 的 3 项 SQLite 条件在各自对应环境运行；两个环境各跳过 1 项专用 Redis 检查。队列传输未改动，沿用此前独立 Redis/Celery 专项 1 通过。Ruff、316 文件格式、86 源文件 mypy 及 diff 检查均通过。
- 后台 310 单测及 6 项相关 Chrome 用例、小程序 625 单测与本地 H5/微信构建均通过。原 450 KiB 限制下，test / production 主包分别为 459435 B / 458354 B。最终定向复审核对 5 项及 1 项显示收尾全部关闭，真机 PDF、耳机与系统面板仍待验。三仓为本地 test 提交，未推送、部署、迁移远程数据库或上传 OSS/微信。


## CHG-0040 测试发布（2026-11-10）

追加授权后已推送 test，固定 API 139ad6d 部署测试 7 服务、全部 healthy；官方 MySQL/Redis 804 通过/3 跳过，双镜像与公网/契约验证通过。测试库停写备份后 0026→0027/contract3，原 56 表原字段与行数一致、统计新表为空，12 个非目标容器不变。微信开发版 1.5.0-test.20261110.201701 已上传，体验版用户手动切换；实际 SDK/接收关闭、正式全文缺失保持 legacy。详见 [发布回执](../verification/chg-0040-test-release-20261110.md)。

## 2026-11-11 CHG0041 API本地增量

0028批次/明细扩展、冻结跨页集合与逐项任务回执、failed子集重试、AccessHistory关联已完成。统计固定关闭旧开关与新v2披露。SQLite768/57、真实独立MySQL821/4、ruff/mypy通过；未推送部署或改原环境。配套admin317、mini826及check/build通过，Chrome10项Mock矩阵和2项真实API/worker/H5联调通过。原本地库只读备份副本0027→0028，58旧表911行原列摘要不变且原文件SHA不变；原生Chrome125%/微信真机/真实友盟留待验。

## 2026-11-11 CHG0041 审查统一修复

R1共享失败终态收敛覆盖fail/claim，真实worker外层临时耗尽、非临时失败及旧lease保护回归。完整SQLite771/57、真实MySQL批次/jobs18、ruff/mypy通过。配套后台R2/R3只读恢复围栏与公开Pinia身份代际、mini R4允许许可文案均通过完整322/829测试及构建；未扩大操作范围。

---

---


## 2026-11-05 部分匹配高亮生产发布

按用户新增授权发布13c2d4c：官方CI真实MySQL/Redis633通过/3跳过，生产管理三服务及听读Worker共4服务healthy，其余15容器保持；库0025/contract3无迁移，483任务/231日提交计数及全部词轴摘要保持。《银行》公开API仍ready/118词/revision2。无新增ASR调用、无文章重发布及小程序上传。详见 `docs/verification/listening-partial-production-release-20261105.md`。


## 2026-11-05 管理后台与接口 test 合并 release 并上线

按用户授权完成两个仓库合并、远程 release 推送及生产原生部署。后台 286 测试通过；API 官方完整 CI 644 通过 / 3 跳过、双角色镜像成功。7 生产服务健康，数据库 0025/contract3 不变，无迁移或新增 ASR；测试及其余基础设施保持。固定源码、公开边界及无密钥证据见 [发布记录](../verification/admin-api-production-release-20261105.md)。
