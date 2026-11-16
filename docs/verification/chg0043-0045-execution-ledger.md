# SDD ledger — plan: docs/superpowers/plans/2026-11-15-chg0043-0045.md

用户2026-11-15批准执行；三仓test基线见Spec。原始checkout保留，开发使用原生工具创建的test基线worktree。

| 检查对 | 共享范围 | 结论 |
| --- | --- | --- |
| Task1自身 | 类型/发布/PDF/导入/统计/队列 | Spec统一；未就绪兼容旧读取，新发布按明确类型校验 |
| Task2自身 | 页面/选择/分页 | 以成功响应提交状态，失败保留 |
| Task3自身 | 列表/来源/身份 | 同类型过滤，复习不加未完成限制 |
| Task4自身 | 验收/报告 | 区分真实和模拟证据 |
| Task1与2 | OpenAPI/后台接口 | 后端先导出准确交接，前端生成类型 |
| Task1与3 | OpenAPI/类型/来源 | 后端先导出准确交接，前端生成类型 |
| Task2与3 | 无共享源码 | 均依赖Task1契约，保持暂停开关 |
| Task1至3与4 | 提交和测试证据 | 完整范围审查，不冒称真机 |

Ruling: 用户已批准执行，不再次请求计划或执行方式确认 — 延续本轮授权 — 有问题可本地修订
Ruling: 使用原生worktree基于test，保留原checkout — 隔离可回退 — 交付提供准确位置
Task1: pending, base 82a436242c3332c46fd78f7367b27d24f203522f
Task2: pending, base 97bd6ea7b2fc34edcb6e516933e7eb1e5d86e3f5
Task3: pending, base 56ded7b33aaa1883bef4d7a39bfa0b72eae44135
Task4: pending

前端隔离目录：/Users/lubi/.codex/worktrees/chg0043-0045-admin/juya-admin；/Users/lubi/.codex/worktrees/chg0043-0045-miniapp/juya-miniapp
基线：Node22.23.3，pnpm11.25.0 frozen install通过（simple-git-hooks在linked worktree提示ENOTDIR，未改共享hooks）；后台63文件322通过（既有jsdom pause提示）；小程序142文件862通过。日志/tmp/juya-chg0043-0045-{admin,miniapp}-baseline.log
Task1 implementer /root/implement_api，进行中，首版契约已写。

真实验证服务：Oracle MySQL8.4.11，独立/tmp/juya-chg0043-verify/mysql-data，端口52982；Redis7.4.11端口52897；私有环境仅/tmp/juya-chg0043-verify/test.env，已通知Task1实现者。权限只限juya_verify；root口令未输出。

用户新增授权：开发验收通过后推送配套test并部署测试环境及部署后验证；生产不操作。Spec和Plan此前的禁止测试发布由此次授权覆盖，仍须先完成开发与验收。

后台浏览器基线：Chrome headless，现有content-lists-element-plus和free-access-batches共14项通过（/tmp/juya-chg0043-admin-browser-baseline.log）；既有Vite ResizeObserver loop通知出现在几何用例中，不能声称基线零警告。

Task1实现中核对：content_types.type_issues的未就绪豁免可能允许无类型新发布，已要求实现者按Spec移除发布豁免并显式修正测试夹具；旧读取兼容保留，不自动填真实分类。

Ruling: 后端契约已固定，前端两仓只读契约副本并在各自隔离仓库并行实现，使用dispatching-parallel-agents处理独立问题域 — 无共享写入且后台MySQL仅API实现者使用 — 若契约再变更需重生成并联调验证。SDD逐任务审查门禁保留。

Task1: implementation reported DONE, commit7324f43371c926e964eb6beda840cc6182d446d0, awaiting review /root/review_api。SQLite822/58环境跳过；MySQL/Redis全量876/3SQLite跳过；最终PDF补丁真实MySQL/Redis专项81/0；static/OpenAPI通过。源码审查包review-task-1-source.diff，完整包review-82a4362..7324f43.diff。
Task2 /root/implement_admin 进行中，最新343单测/check及17Chrome通过，扩展导入/PDF浏览器验收中。
Task3 /root/implement_miniapp 进行中，887单测/27组H5视觉已验证，最后就绪撤回边界与构建复验中。

Task1: review /root/review_api Spec issues/needs fixes，7 Important（词形双写误配/同处义项冲突/空释义发布/position复用漏判重/听读v2候选恢复漏判/旧跳过事实随目标删除丢失/异常原文被批量补空）及1相关Minor来源标记；原实现者fix round1/5进行中，base7324f43。旧source_hint缺字段类型only往返与两坐标重定位已由审阅者独立验证正确。
Task3: commitdb6ae64，142文件890测试/check/双构建及27组视觉通过；审查1 Important：完成未知直接返回列表未查原回执，原实现者fix round1/5进行中，basedb6ae64；其余已审范围无明确缺陷。

## 集成和发布接续

用户要求开发验收后直接部署测试，已明确接受推送配套test。不要再次询问已有授权；生产不操作。
三个原生worktree均detached，最终在原github-repos三仓test安全快进并推送（不强推）；原API checkout有本轮初稿spec未跟踪，快进前先将原字节备份到私有位置再用已提交新版替换，保留其他变更。原本地配置/服务保留。
本地工具：PATH需加 /Users/lubi/Desktop/juya/.tools/node-v22.23.3-darwin-arm64/bin、.tools/uv/bin、.tools/ffmpeg/bin；pnpm11.25.0。独立MySQL52982、Redis52897，私有连接配置/tmp/juya-chg0043-verify/test.env（不可输出），仅限juya_verify；最终清理只停止本轮创建的PID（mysql47693、redis47616，先核对进程身份）。
真实浏览器包在admin worktree node_modules/@playwright/test，Chrome channel chrome；原Chrome/原开发服务不要停止。Task3自用5186已停止。
本轮尚未启动真实HTTP联调服务/种入联调数据；前端已完成的浏览器验收都是隔离Mock，不能冒称真实API。Task4需补真实前后端联调，实际微信/iOS/Android真机不得虚称通过。
发布工具原仓 /Users/lubi/Desktop/juya/github-repos/juya-cli，配置github-repos/.local-release/config.json；CLI要求test分支干净/已同步。无本地Docker，API通过官方GitHub CI双角色镜像制品发布。GitHub插件可查commit combined status和下载run artifacts；fetch_commit_workflow_runs仅PR过滤，不能查test push全量。GitHub SSH22失败时已验证git -c core.sshCommand='ssh -o Hostname=ssh.github.com -p 443 -o ConnectTimeout=10 -o BatchMode=yes'可fetch（不改全局配置）。
最近umeng-test-release-20261115记录过镜像解压/导入导致共享盘压力和生产worker自动重启，最终仅约5GiB空闲。发布前必须只读核对当前空间和存储放大、运行/回滚镜像引用，不能全局prune或清生产资源。测试迁移0028→0029须优雅停写、备份与SHA验证、原60表原字段/行数/指纹前后比对、新字段为空/新表符合预期，再恢复服务/维护开关，沿现有原生发布引擎。
当前未读取任何真实服务账号/密钥；后续需要SSH/GitHub/测试后台时先从统一账号相关.txt读取对应服务/环境所需资料，禁止输出密码/令牌。测试小程序使用标准release:mp-weixin:test（含测试OSS），体验版由用户切换，禁止生产发布。
历史归类不能按PDF静默回填；测试部署后如有旧发布卡，应生成真实建议清单并取得管理员明确确认再启用，不猜测异常附件，不操作生产历史。若需用户选择，先把具体列表做到可审阅，再async问分类确认，其他测试部署继续独立推进。

Ruling: 驳回Task1 I3“场景空释义应阻止发布”，不收紧该选填规则 — 已从20261106完整需求XML段102/511/700/1243核实多处明确场景释义选填，当前合并需求P57要求各模块原规则保持；听读有词条时释义仍必填 — 若错误会保留不合规则的空释义发布，但原文证据明确；API实现者已要求独立撤回I3改动，6项Important和来源Minor继续修，Spec/Plan已澄清。审阅者已排队通知，下次复审核对并更正原报告。

Task3: fix round1/5 complete（I1 addressed，0 open，db6ae64..6e618b1），/root/review_miniapp限定复审Spec compliant/quality approved。定向73、全量898/check/双构建通过；复审另定向8项通过。Task3本地完成，仍需Task4真实三仓联调/整体审阅和部署。

Task1: fix round1提交877f09e，六项Important+Minor实现者报已修，I3依真源驳回，SQLite832/58环境跳过、真实MySQLRedis887/3SQLite跳过、static/OpenAPI不变；/root/review_api正在限定复审（task-1-rereview-1.md待回）。
Task2: 提交eb24925，本地350单测/check/build/28Chrome通过；/root/review_admin发现3 Important，原实现者fix round1进行中：免费筛选失败选择过早clear、合法引号来源前后端分句不一致、听读回退导航等待后迟到覆盖新分类。完整独立复现在/tmp/chg-admin-review/。
Task4真实HTTP联调已启动：/tmp/juya-chg0043-live.py使用tests/conftest隔离SQLite自动夹具，运行目录由/tmp/juya-chg0043-live-location指向（无真实业务库/账号），admin19043、mini19044；tests媒体worker已真实处理PNG/WAV/PDF，不接真实微信/云网关。会话session91986持有HTTP fixture进程；Vite admin5197 session2744，H5 mini5187 session36654，均本轮创建，原服务保留。
自动Chrome脚本/tmp/juya-chg0043-http-browser.mjs已完成7组真实HTTP流程，结果/tmp/juya-chg0043-http-evidence/results.json，0HTTP失败0页面异常，截图同目录：管理员登录38正式卡/24听读、手动跳页普通清选、跨页免费、1个合成历史卡明确确认并启用、图解26统计不随标题空搜索变0、听读末页4条、H5游客图解26/精读12。只使用本轮自动fixture账号；不是用户本地手工验收或真实微信。尚未测试ZIP全链/实际发布编辑/错误故障注入，后续修复后补验证并最终归档。

Task1: fix round2/5 complete（R1 addressed，新R2 open：go/do复合词错误规则；877f09e..52d606d），原实现者完成第3轮，限定审阅确认fix round3/5 complete（R2 addressed，0 open；52d606d..904afb4）。Task1本地完成，Spec compliant/quality approved。最新SQLite929通过/58环境跳过、真实MySQL业务166通过、static/双契约不变；最新完整MySQLRedis留官方CI核对。
Task4真实ZIP全链已补：/tmp/juya-chg0043-import-http.py上传实际DOCX/PNG/WAV ZIP，7次真实worker解析处理，批次3张=2待核对+1重复；真实Chrome恢复批次→明细显示文件夹→默认类型只补1个缺项→未知原文仍待单项明确→排除未知→真实import.save保存1草稿、跳过1重复、排除1。证据/tmp/juya-chg0043-http-evidence/import-results.json及real-import-{review,saved}.png。非Mock，不涉及真实业务账号数据。
HTTP fixture最初进程6638已确认独占19043后停止，使用/tmp/juya-chg0043-resume.py从原隔离test.db重开，session5755，最新API904afb4；保留现有测试记录。旧失败seed进程5905仍存活但无端口，清理时只核对该本轮进程再停。

Task2: fix round1/5 complete（I1/I2/I3 addressed，0 open；eb24925..cea5772），独立限定复审Spec compliant/quality approved。最终67文件366测试/check/build、相关11Chrome通过。
Task4: 真实HTTP在API904afb4+后台cea5772完成ZIP草稿实际预览发布、精读缺PDF保存候选但阻止预览、图解带PDF须明确移除才可发布、She bought tea!”买词形来源的真实听读预览发布。editor-results.json无页面异常；已归档选择性截图和无秘密结果至docs/verification/chg0043-0045-local-http-20261116/，52项台账分开自动化/远端/真机边界。
Ruling: 沿用户“开发完直接部署测试”既有授权，最后采用安全快进原test并推送/发布测试，不再次弹集成选项 — 与用户明确目标一致 — 若误解会把通过门禁的更改发布到测试；生产范围不扩大。精确相同源码已有冻结全量证据，文档归档不重复整套测试，官方CI会对推送SHA再次完整MySQLRedis核对。
Task4 final review: With fixes，0 Critical/3 Important/1 Minor。I1冷启动未知完成无持久body卡两栏，I2明确移除PDF版本ID误示有效附件，I3 dye/singe规则误配。Minor历史确认ESC/X残留pending行冻结；与I2同组件纳入唯一最终修复波。完整复现见final-review.md，单个新实现者修完整清单，不将同一审阅分拆多波。
Declined to judge逐项处理：场景释义选填依真源不改；合法重叠和独立位置保留；就绪前准备中符合启用次序；未知完成自动刷新只读保留（I1只补用户可达显式恢复）；真实历史归类不代签；暂停权限保留；真机/最终CI/远端部署作为后续证据如实登记，不将未验伪装已通过。这七项与Spec/既有用户决定一致，无额外产品范围。

Task4: 最终唯一修复波完成，API8f3f25c..143fd38、admincea5772..7446218、mini6e618b1..46d9b7e。原I1/I2/I3及相邻Minor均ADDRESSED，final-rereview.md Ready Yes，0新问题/0范围外问题。冻结API945/58环境跳过、真实MySQL专项168；后台370、小程序905、静态构建通过。根真实HTTP最终143fd38/7446218补验两张明确移除PDF的历史附件及ESC后改选，无异常。
三原test checkout已安全快进并push：API143fd385b382a51504be90d9cd8e5cb2d6bf0cd4、admin7446218001c5da66e162497e21280dfbfeac7bf9、mini46d9b7e2d64e73aed0a38f3a53e06128fc135e97。原API未跟踪初版Spec已按原字节SHA备份私有original-checkout-backup，无其他改动丢弃。最终源码官方CI run43742494469，quality进行中，未宣称通过。
Ruling: 最终两角色API共享同一原test源码且recipe.checks逐字相等，原生publish.run_checks仅执行一次完整门禁，按源码完整SHA和checks摘要冻结成功收据；两份制品随后分别走原生verify_artifact/build_bundle，并逐次重验clean test/原SHA — 避免相同环境相同源码的重复全套，所有实际不同制品仍逐份核验 — 若等价检查错误会漏掉角色独有检查，因此入口显式断言同repo及checks完全相等，任一不等立即拒绝；官方CI仍分别构建两角色并完整MySQLRedis核对。

## 当前发布接续（2026-11-16 01:50）
- 原三仓test已push最终源码：API143fd385b382a51504be90d9cd8e5cb2d6bf0cd4/admin7446218001c5da66e162497e21280dfbfeac7bf9/mini46d9b7e2d64e73aed0a38f3a53e06128fc135e97，均原checkout clean；API managed worktree有未提交最终归档文档，留发布完skip-ci提交，不能因此把部署源码SHA变成未打镜像的文档SHA。
- official API CI run43742494469（https://github.com/zhanjiangmrlu/juya-api/actions/runs/43742494469），quality真实MySQLRedis pytest进行中，双image job须全success后取制品。读取 /tmp/juya-chg0043-ci-state.py 经 /tmp/juya-chg0043-remote.py 可安全查状态到/tmp/juya-chg0043-ci-current.json。Github连接器push查询不足，remote官方API私有token只在server进程内读取。
- 统一私有发布目录 /Users/lubi/Desktop/juya/github-repos/.local-release/private/chg0043-0045-test-20261116，test-only config.test.json有现存mini dictionary overlay（准备者先前读取摘要误判，已更正，未改全局配置）。
- 管理后台已用原生node CLI build通过check/370单测/build，web-bundle.json已冻结：/Users/lubi/Desktop/juya/github-repos/.local-release/runs/20261116T014136-5e1546/juya-admin/20261115T174223-7446218001c5-149624/juya-admin.tgz，SHAfee522e515d11720f591004070f2d995f20bf0a2e01be7048527cb4d1afdcf17，profile私有juya-admin-profile.json。尚未部署，待API完成。
- 原生API共用checks正在原test上执行，session66269，脚本private/native-api-bundle.py checks，日志native-api-checks.log。必须用API .venv/bin/python（默认python3是3.9，import datetime.UTC不支持；首次在import阶段失败未运行测试，已改3.13正确重启）。checks成功生成native-api-checks.json才可bundle；两角色recipe.checks逐字等同已有强断言、source_version固定clean test/143fd38。artifact归档放private/artifacts/juya-{admin,miniapp}-api后调用同脚本bundle，分别走原生verify_artifact/build_bundle并保存role-bundle/profile JSON。
- 远端仍未写入/部署/迁移/清理。root askpass /tmp/juya-chg0043-askpass.py只给SSH调用不可直接执行；/tmp/juya-chg0043-remote.py --script 本地脚本 --output 私有输出 可安全远程python，stdout直写600文件，屏幕只exit/bytes。/tmp/juya-chg0043-scp.py --destination /root/juya-rebuild/ci-images/chg0043-0045-... files... 安全上传；仍未调用上传。
- 私有readiness目录 .local-release/private/chg0043-0045-readonly：完整runbook已复制test发布private；controller最终SHA7fb6899981537bb9215f25108a34863eeb23a005d86b40de86ce25ba441cfb58，本地syntax及空receipt拒绝通过，补充pre-migration失败恢复/显式resume无backup例外，migrate_attempted前持久标记。receipt.template.json须填完整固定SHA/profile/bundle/镜像ID/旧指针/阶段磁盘门槛/保护资源401 URL/OpenAPI canonicalhash。controller分plan/preflight/gate-backup/migrate/deploy/verify/resume/finalize及rollback；只root逐步执行，先完整dump备份下载本地hash相等标记backup_verified才migrate。7目标与12保护容器精确ID/StartedAt/restarts比较，生产不操作。
- readonly docker-layer-baseline.json含19容器/4镜像完整RootFS链32diffIDs，同分区空闲8.1GB；候选CI镜像必须实测。/tmp/juya-chg0043-layer-budget.py ARCHIVE --known baseline --output JSON逐层hash验证+完整父diffID链判复用+4K分配上界，逐阶段预算3GiB安全余量。不可仅按gzip估计。若不足，test-cache-plan.json提供3份精确冗余传输归档可删总513174980B，未删，必须重验引用/hash；不得碰备份/安装currentprevious/镜像/prod/globalprune。必要时可研究清理自己controller candidates重复暂存但原生manifest需完整，不能随便删已安装文件；以实际候选测量决定，不先做猜测优化。
- /tmp/juya-chg0043-artifact-stream.py模板填ARTIFACT_ID/EXPECTED_SIZE/DIGEST经remote.py将官方ZIP流到本地（server不落盘，不向重定向站携带Authorization），本地核官方digest/严格ZIP成员及原生镜像identity。未运行下载。/tmp/juya-chg0043-transfer-file.py用于后续备份安全流下载，未运行。
- 微信工具islogin=true已实查，仅最后标准pnpm release:mp-weixin:test上传开发版+testOSS，体验版用户切换，未上传。
- 真实test历史48有发布指针，其中当前有效15、PDF5、异常0。私有test-history-classification-review.json及历史场景分类待确认.md已生成；已async问用户5指定精读+其余10图解并启用，尚未回答。必须等明确确认才正式接口归类，绝不自动按PDF写。该问不阻止技术部署。账号资料文件test域名段没有明确test后台账密（只找heading/label，未读prod密码）；若需要登录并缺匹配test凭据按AGENTS向用户补问，不拿本地或prod密码猜。
- 原始own HTTP/Vite/mini进程已按PID+命令核对后停止：7420(5187),7423(5197),25188(API19043/19044),5905(失败旧seed)；fixtures/evidence保留；原用户服务未手工停止。本轮MySQL47693(52982)/Redis47616(52897)尚留，最终只核身份再停。
发布检查环境纠正：原仓.venv的editable juya_api.__file__实际指向旧 /Users/lubi/.codex/worktrees/juya-api-integration08/...，导致原生pytest加载旧业务代码的大批失败，已在79%前主动中断，不把该运行称通过；原venv/本地.env均不改。私有source-workspace/juya-api以git clone --shared --branch test从原仓获取相同143fd38，uv sync --frozen建立独立绑定当前clone的.venv（不带被忽略本地.env），实际__file__核对正确。缺类型发布定点用例先验证clone，再以相同原生run_checks整套重跑。native-api-bundle.py已固定SOURCE为private/source-workspace，同时校验原仓和clone均clean test/143fd38，两角色build_bundle也使用该等价固定源码。独立源码树SHA一致，不绕过失败门禁；原始失败日志保留native-api-checks-stale-binding.log，真正成功收据只有完整check全过才生成。
正式检查纠正后验证：private clone完整原生release gates成功，945 passed/58 skipped（273.71s），Ruff/format/Mypy通过，native-api-checks.json成功收据已生成。原session81798退出0。不得重跑相同checks；等CI制品后用clone .venv Python运行native-api-bundle.py bundle，入口会校验receipt/两源版本/逐角色artifact。
真实受保护资源401 probes已只读从旧test数据库取当前有效PDF+场景音频+听读音频，private-resource-probes.json生成3条URL，无凭据、无业务写。current-pointers.json已只读采集原testAPI/web current/previous、引擎revision、docker storage driver及nginx哈希；controllerpreflight仍须再次断言。
2026-11-16 02:07官方CI全部成功：run43742494469，quality1000 passed/3 skipped（1039.88s），jobs132898501943/132903798382(mini)/132903798393(admin)均success。制品14172973572(admin,250342003B,官方ZIP e37614958f2d61943e29025caf62b542415ffb2ae6f730f0c499c630ec877223)及14172938589(mini,250322722B,ZIP350b999fb6c9b9cdaf5594ad933a7e9d8fd0847c814d7d525ab05fb579f67993)已通过连接器下载至private（最初server中转慢已停只读传输，无远端落盘；不要再输出signed文件URL）。verify-official-artifacts.py已严格ZIP/官方digest及原生identity验证成功。admin tar973aa453f6b9af77ecf211aab6513a89f9287b5faa187ad91f102a0e1cad49e3 configIDsha256:569042d25f03b239d369dd6da8809586248d2859879459bb15bef844b90169cb；mini tar81089297214b2f883d9b028a16a7beb6c510b21d2aed845045bf4b71f0ecd340 configIDsha256:e520f77f3f3c9a3a7506cb10343d90b55234da5182382be44bc753b999f7719f。二者source均143fd38。
原生bundle构建session64105在private/native-api-bundle.log；脚本native-api-bundle.py bundle只走两个逐份verify_artifact/build_bundle，不再跑checks。/root/prepare_test_deploy已恢复只读工作，测实际C/U/L与阶段budget，输出private/budget-proof.json，根等此门禁后才stage任何远端文件。server已确认Python3.12.3/engine45ff9c...，Docker overlayfs+containerd snapshotter（别盲目把OCI blob暂存当无压缩tar，须证明或保守）。realtest归类用户仍未回答，尚无分类写入。
2026-11-16 02:24后开始ECS本轮写入：已在预算首次实时检查通过后创建唯一/root/juya-rebuild/ci-images/chg0043-0045-test-20261116-143fd38，free8085643264B >= needed8066514944B。原test服务尚运行，无维护gate/迁移。最终controller bda9cc1127c516356f740f38b4635e1ffee5dffcc2c1ae3c65fdb3fe09283d95、proof551b9944173789782451bab0e2d6107650bdf58239e2fcbbd819fdc982fa1fa2，private/receipt.json已完整冻结含measurement_path、migrate:identity等门槛。预算无旧资源删除credit，仅migrate身份核验后清本轮两个再生candidates，保留完整native tgz/profile；后台web tgz必须API finalize后另传。root只上传API两tgz/两profile/controller/receipt/proof共7文件；api-upload-manifest.json已记每个本地路径/remote basename/bytes/SHA，当前传输会话以工具返回为准。初始实际边际19MB是在预留3GiB+64MiB备份+210MiB新日志+96MiB额外之后的再余，必须每步实时门禁，SQLdump>64MiB时不得标backup_verified。
实际传输阻塞与替代：root SCP session23334启动后约8分钟仅首包72MB/500MB，未停写/未load/未迁移；已按父子进程身份终止本轮scp的ssh，私有batch留一个未验证部分tgz，其他原资源不动。准备者正实现早期transport：服务器从fresh GitHub connector文件引用取官方ZIP（私有URL不输出），校验official ZIP digest和inner image.tar.gz SHA，插入小TAR envelope（本地原生冻结包的prefix/suffix、原gzipheader/trailer）以level1重建同一native tgz，必须完整原5ddf/b821 SHA匹配才atomic replace，不修改冻结包/检查。早期阶段无Dockerload/newcontent/snapshot，双role顺序临时峰值约1GB+3GiB+既有余量 <原全局8.066GB，完毕即清本轮ZIP/raw/part再preflight；proof runtime条件将更新，receipt/core和wrapper需以新measurementSHA重签后上传小文件。不要继续等原慢SCP或当部分tgz为完整。此为完全同字节包的传输修正，源/原生校验不变。
02:46运输修正首包真实成功：server直接从连接器官方ZIP下载，officialZIP+image.tar.gz+原TAR+原gzip CRC/size/full native5ddf6d83d09e4156862b2ce74ab445395cb89343e44ced54ae351a749f1d116c全部一致，serverzlib1.3与local1.2.12实际全包字节相同。旧未验证部分tgz已atomic replace，首包ZIP/raw/part已删。rootlocal private/juya-admin-api-transport-result.json保存完整安全回执。root开始第二role同流程，仍未image load/gate/DB写。
运输proof已更新e7bebccf9c3335d2870eb60fccd51839d680d67174444573d3da3eb12547f45f（追加早期阶段临时峰值1.004GB，连3GiB+其它额外4.613GB，低于全局8.066GB），controller bda9...不变。receipt.json measurementSHA已重签小文件/两个profiles/controller/helper/envelopes/final7manifest已上传。scriptprivate/transport-rebuild.py SHAee82d541616f113c5b6ba25138449916dbb94f0c680ee3f77bf17fa2382505e8；两个小envelope约45/43KB。server所有URL只600文件、wrapper结束会删；不要输出signedURL。adminwrapperserver-transport-admin.py，mini按project常量生成server-transport-mini.py。下一步等mini成功后server helper --finalize-only --final-file-manifest api-final-files.json，核完整7文件和无.transport临时，再明确执行server-step-preflight.py（已按新receipt core重生成，core2cd?现以当前文件实际为准）。
02:53首次preflight在外层controller锁尚未建立目录时FileNotFoundError退出（native api._lock要求给定root已存在）：controller-lock/.artifact-deploy.lock。经安全trace确认尚无controller-state/gate，未到任何Docker import/SQL步。根仅创建本轮root/controller-lock 0700，未修改冻结controller/proof/receipt/包，补齐native锁前置目录后重试同一preflight。其余原服务/数据库保持旧状态。原生API每项目锁依然照常执行，不跳过锁。

## 真实发布维护阶段（当前继续点）
19:00UTC gate-backup成功：gate_active=true，原test 7服务优雅停止；其他12保护容器精确不变。data-before包含60表原列序/count/SHA，schema0028/contract3。完整juya_test备份12815776B，server/local SHA同为63292f67b49c3d5777b17569c785d2595580e2b6810d2d4c7418d02c084db57b；私有local backups/juya_test-before-0029.sql（600，勿输出内容）和server backups同留。server-backup-evidence.json已包含baseline/data-before/backup receipt，只有哈希无行值。根确认完整dump和scope后通过receipt.updated.json小传输、server-confirm-local-backup.py核core/sha一致并atomic replace receipt.json；backup_verified=true，源码core未变（marker排除在core外）。初始7文件manifest用于preflight，receipt备份marker允许更改后不要再用旧7清单判断receipt。
19:04UTC migrate明确成功：step-migrate-result.json exit0/migrate_attempted=true/migration_complete=true/gate_active=true，原生0028→0029且contract3，60表原字段顺序、行数、全值指纹比较成功；new type表空/新投影NULL/removed_count0，未历史归类。migrate身份检查后只清本次2个candidates已做，候选目录现空，原生tgz/profile均保留。
当前deploy显式会话71839正运行 /tmp/juya-chg0043-remote.py --script private/server-step-deploy.py --output private/step-deploy-result.json --timeout3000（两角色原生publish及第七listening worker），必须等其完成/查真实state，不重复启动。待exit0+deploy_complete后依次运行server-step-verify.py→server-step-resume.py→server-step-finalize.py，每步单独判断成功才继续。verify保持gate，校7健康/source、60原字段、3真实受保护资源401/角色边界/OpenAPIcanonical、12保护容器；resume才恢复nginx原始字节，普通流量再probe；finalize原生保留策略，生产保护/备份不清。
源API143fd38/admin7446218/mini46d9b7e均test已push，official CI1000/3，静态与双镜像all success。controller SHA仍bda9cc...，proof最新e7bebccf...（早期运输增强后），receipt.json固定源+profile+bundle+阶段budget，backupmarker已true。当前技术部署未完成，不能提前final；test gate仍active。若deploy失败，诊断fixed stagecode/私有trace后按既有controller rollback（保留gate）→严格recovery验证→显式resume，DB不downgrade/不自动SQL restore。

Task 1: complete (commits 82a4362..143fd38, review clean)
Task 2: complete (commits 97bd6ea..7446218, review clean)
Task 3: complete (commits 56ded7b..46d9b7e, review clean)
Task 4: complete (final review and one scoped fix wave clean; technical test release verified)

2026-11-16 03:32最终只读复核成功：7测试服务143fd38健康/0重启，12保护容器精确不变；维护配置原字节恢复，data-resume与data-before原60表相同，schema29/contract3。API native finalize成功（正常删除两份Nov12旧test release及镜像引用，无warnings）。后台7446218安装76文件、公开50文件SHA一致；小程序46d9b7e标准test上传1.5.0-test.20261116.032311，测试OSS新增0/复用13，277构建输入核对。历史15张未归类/启用，content_types_ready=false，用户仍待确认清单。真实微信/iOS/Android及远端后台账号业务未验。详见版本化测试发布报告。
本轮独立MySQL47693/Redis47616核对命令及端口后SIGTERM清理完成，原用户服务未停。受控私有备份及审计保留，原生外部管理worktree保留。
