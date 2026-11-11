# 小程序横向布局与授权展示修复包（2026-11-11）

用户反馈测试画面后，小程序test补丁1413ad4修复听读横向溢出/换行、列表顶部未授权及笔记卡片授权可学残留，共用播放器去除普通暂停时的高亮/尾迹提示；140文件844测试、check、H5/微信构建及浏览器320/390/430边界验证通过。

已推远程test并标准上传小程序测试开发版 **1.5.0-test.20261111.184518**，体验版由用户手动切换；真实手机左右手势待复验。本次仅小程序更新，API继续使用81f8776，无新增后端部署/迁移或数据改动；生产保持。完整说明及无密钥回执见小程序docs/verification/listening-layout-authorization-20261111.md与配套JSON。

---

# 学习授权暂停测试发布与开发版（2026-11-11）

用户本轮明确授权后，API及小程序已推远程test；测试双API/Worker/dispatcher与独立听读Worker共7服务部署81f8776并健康，官方CI834通过/3SQLite专用跳过。juya_test已备份，无迁移，schema0028/contract3、60原业务表全部字段与行数及授权记录保持；12非目标容器不变，生产与原本地服务保留。

标准命令已上传微信测试开发版 **1.5.0-test.20261111.170119**，源码1dfa0d3，20页/3Tab，测试OSS新增0/复用13。实际包仅测试API，包含更新协调器，真实统计关闭。**体验版未切换，由用户手动操作**。无新增埋点，sample.txt未改；原生选词和真实版本下载/重启待真机验收。完整结果见配套API docs/verification/learning-pause-test-release-20261111.md及JSON。

下文“仅本地/未推送部署”为发布前历史阶段。两项MySQL专用保留查词并发测试夹具遗漏已在81f8776补齐，最终官方全量通过；产品暂停规则保持。

---

# 学习授权暂停与更新提示（2026-11-11，仅本地）

按用户确认方案在 test 实施：所有身份仅学习明确免费的已发布内容，非免费统一“暂未开放”；授权与内置查词代码/数据保留，通过集中开关暂停。账号学习授权区域和请求隐藏，正文系统选词；主题听读关闭动态高亮与自动跟随，保留精确静态色带。新增应用级下载就绪更新提示，取消后下次进入再提示。

API完整780通过/57条件跳过，隔离真实MySQL针对性110通过，ruff/mypy通过。配套小程序139文件840测试、check、H5/微信local构建及主包预算通过。独立审查P2词内静态范围着色已按连续样式片段修正并回归。无迁移/新增埋点；未推送、部署或上传。iOS/Android原生选词及真实微信升级尚待真机验收，不能将自动化冒充真机。详见配套API docs/verification/learning-pause-20261111.md；恢复开关见各仓本轮说明。

---

# CHG0041 测试发布与开发版上传（2026-11-11）

用户本轮新增授权后，三仓已推远程test；测试双API及Worker/dispatcher、独立听读Worker共7服务全部healthy，固定API364317c；后台bdefc6a已部署，73安装文件与48公网文件哈希一致。测试库备份后0027→0028/contract3，原58表全部原字段与行数保持，仅新增两张空表；其余12容器及生产保持。

官方CI42962582010真实MySQL/Redis825通过/3SQLite专用跳过，双镜像通过。后台check/322测试/build通过；公网双ready200、鉴权/角色/游客/OpenAPI核验通过，v2正式隐私/统计说明生效，真实统计能力false。标准流程上传微信测试开发版 **1.5.0-test.20261111.133729**，源码72914e0，20页三Tab，测试OSS新增0/复用13，官方成功回执已核对。**体验版由用户手动切换**，未提审或正式发布；原本地热更新保留。详见配套API `docs/verification/chg0041-test-release-20261111.md` 及无密钥JSON。

下方“仅本地/未推送部署”为此前开发阶段历史；原生125%、微信真机和真实友盟收数不在本次发布中冒充通过。

---

# CHG0041 独立审查统一修复（2026-11-11，仅本地）

R1补齐所有任务失败终态：通用fail与claim租约耗尽共用pending明细收敛，处于原管理员/Job锁与lease保护内；只归类pending，不改成功回执。真实worker外层异常临时重试耗尽和一次非临时失败、旧lease拒绝、失败子集可重试均通过。修复后SQLite完整771通过/57环境跳过，独立真实MySQL批次/jobs18通过；ruff/mypy通过。原完整MySQL821/4及Redis1为修复前主体回归证据，未将focused18冒充全量。

配套后台322测试/check/build及NODE_ENV=production真实Pinia5项通过；小程序829测试/check/H5/mp-local/meta预算通过。详情见[审查修复验收](docs/verification/chg0041-review-fixes-20261111.md)。本轮不推送、部署、上传、操作原库/原服务，原生125%/微信真机/真实友盟未验边界保持。

---

# CHG0041 本地跨页免费与统计收紧（2026-11-11）

现有test分支增量：统一跨页免费preview/accept/read/retry，冻结完整选择、跳过与失败分开、逐项事务审计、租约重投幂等；0028仅新增批次和明细两表，最低schema28/contract3。统计旧客户端开关固定失效，真实能力及collecting为false；新披露bundle privacy/analytics v2、terms沿用。未推送、部署、上传、修改原配置或业务库。

SQLite完整768通过/57条件跳过，真实独立socket MySQL821通过/4跳过（3SQLite专用、1Redis条件），ruff/mypy通过。见[本轮接口契约](docs/implementation/chg-0041-free-batches-contract.md)。配套后台317测试、小程序826测试、两前端check/build、Chrome10项Mock流程/状态矩阵及2项真实API/H5联调通过；原生Chrome125%和微信真机/真实友盟未验，125%仅CSS布局证据。详见[逐项验收](docs/verification/chg0041-acceptance-20261111.md)。

---

# CHG-0040 审计问题修复与测试发布（2026-11-10）

用户确认公开主体“句芽英语”、隐私联系邮箱 juyaenglish@163.com，并授权保留友盟、如实披露必要自动字段。本轮新增三份完整协议 `src/juya_api/policies/chg0040-20261110-v1.json`；只有测试环境显式设置 `JUYA_PRIVACY_DOCUMENTS_PATH=/app/src/juya_api/policies/chg0040-20261110-v1.json` 和 `JUYA_ANALYTICS_CLIENT_TRANSPORT_ENABLED=true` 才公布客户端统计能力。生产配置拒绝该开关，默认继续关闭。

事件接口保留可信账号、当前协议与许可版本、五类事件、业务回执及持久去重校验；测试客户端模式的 accepted 仅表示本次事件获授权，不代表友盟已收到。collecting 在通道关闭或无许可时为 false，客户端获许可时为 null，实际运行由设备 SDK 状态显示。schema27/contract3 不变，无数据库迁移。SQLite 完整回归 754 通过、56 条环境条件跳过，ruff/mypy 通过；远程官方 CI42837953206 真实 MySQL/Redis 807通过/3跳过及双镜像通过；仅小程序测试端3服务已部署13b5add并全部healthy，其余16容器不变。公网published目录及三正文匿名200、统计能力true、个人隐私401、游客200、后台角色路由404通过；生产未操作，无新微信上传。[无敏感值部署回执](docs/verification/chg-0040-remediation-20261110.json)。微信后台隐私声明及真机仍需按小程序仓库 docs/privacy 指引验收。

---

# CHG-0040 测试发布与开发版上传（2026-11-10，历史阶段）

本次追加授权后代码已推送远程 test，测试 7 个服务已部署固定 API 139ad6d，全部 healthy；测试库备份后 0026→0027/contract3，原 56 张业务表原字段及行数保持，12 个非目标容器不变。官方完整 MySQL/Redis **804 通过/3 跳过**、双镜像及公网/契约复核通过。后台功能无变化，现用安装文件及公网哈希核验通过。

微信测试开发版 **1.5.0-test.20261110.201701** 已官方上传，**体验版由用户手动切换**。SDK/真实接收继续硬关闭，正式全文缺失保持 legacy 必要登录；真实材料生效、SDK 和微信真机不属本阶段完成项。见[本轮发布记录](docs/verification/chg-0040-test-release-20261110.md)及无密钥 JSON；下方“仅本地/未部署”为此前开发阶段历史。

---

# CHG-0040 首次协议与独立统计能力（2026-11-10，仅本地）

本地test新增匿名正式协议读取、可信身份绑定的独立确认、账号统计偏好及五类事件鉴权去重；新增0027扩展迁移，最低schema27/contract3。正式全文未配置时保留legacy必要登录，不伪造新版本同意；真实接收固定关闭，collecting恒false。账号许可与必要收藏/成绩/打卡分别保存，旧设备许可不迁移。

没有推送、部署、上传或迁移远程库。实际8291/8292开发SQLite已先备份和副本试升后分别0026→0027、0025→0027，原56表2565行／55表911行全部原列摘要保持一致，账号和学习历史不变、新统计许可为空。旧local-share的0023接续库因免费名单未知仍保留；未重启原服务。接口及兼容行为见[本轮契约](docs/implementation/chg-0040-privacy-contract.md)。SQLite751通过/55条件跳过，独立临时MySQL22项通过（含0027迁移与并发），静态检查通过；证据见[本轮验收](docs/verification/chg-0040-privacy-api-20261110.md)。真实SDK和微信真机不属本阶段完成项。

---

# CHG-0039 测试发布与开发版上传（2026-11-10）

本次追加授权后，三仓已推送test；7个测试服务及后台已部署，微信开发版 **1.5.0-test.20261110.163037** 官方上传成功，体验版由用户手动切换。API db13c66、后台8516379、小程序e4d8cf8；官方真实MySQL/Redis780通过/3跳过，公网及契约核验通过。schema0026/contract3无迁移，原56张业务表数据及12个非目标容器不变；未执行真实历史数据清理、提审或生产发布。完整回执见同级API的docs/verification/contact-retirement-test-release-20261110.md及JSON。

下方“未推送/部署”为开发阶段历史记录。

---

# CHG-0039 本地开发交接（2026-11-10）

本轮在本地 test 分支取消手机号和微信号收集，采用清空历史值暂留空列，不新增数据库迁移。旧联系方式保存返回410，用户和后台资料/搜索及旧回执不再提供联系信息；小程序旧入口回账号页，保留收藏、授权、学习与友盟统计。

未推送、部署、上传OSS/微信、清理真实业务数据或重新提审。详见 [本轮验收](docs/verification/contact-retirement-20261110.md)。

---

# 整合08生产后端升级与游客访问（2026-11-09）

用户追加授权后，生产数据库及运行配置已完成服务器／本机双份校验备份，再由0025升级0026／contract3；release固定源码b36fc5a已发布生产双API及配套Worker／dispatcher、独立听读Worker共7服务，均healthy、零重启／OOM。官方CI763通过／3项SQLite专属跳过，原55张业务表原字段及行摘要一致，其余12容器保持。

普通公网游客首页、词汇／笔记／听读列表200，个人接口401及角色隔离404通过；临时维护配置完整移除。已有生产小程序1.0.2／102继续使用，未重复打包或上传，体验版用户手动切换；本轮未新增真机扫码验收。见[发布及备份记录](docs/verification/integration08-production-release-20261109.md)与[无密钥回执](docs/verification/integration08-production-release-20261109.json)。下方为历史记录。

---

# 2026-11-09 test合并release

用户本次仅授权将远程test合并到release并推送；本次没有部署、迁移数据库、上传微信或切换体验版。已有release独有提交保留，下方生产／测试发布记录均按原日期追溯，不能将本次合并视为上线。

---

# 整合08测试发布与微信开发版（2026-11-08）

按用户追加授权，三仓已推远程test；测试双API／配套Worker／dispatcher和独立听读Worker共7服务、后台均已部署。API固定5249c04，后台7d32973，小程序6d49d98；官方真实MySQL／Redis763通过／3项SQLite专用跳过，双镜像通过。schema0026／contract3，无迁移，56张原业务表数据及12个非目标容器不变。

微信开发版**1.5.0-test.20261108.071926**已上传，**体验版由用户手动切换**，未提审或正式发布。公网游客／鉴权／契约、后台只读管理员及文件哈希核验通过；原本地与生产保持。见[发布记录](docs/verification/integration08-test-release-20261108.md)及[无密钥回执](docs/verification/integration08-test-release-20261108.json)。下方“仅本地”为此前开发阶段。

---

# 整合08游客体验本地交付（2026-11-07）

当前真源为V1.5整合08／修订17、T01—T379，SHA及历史引用见[需求来源](docs/handoff/revision17/requirement-reference.json)。三仓在原生隔离工作树本地开发；原运行目录、业务数据及配置保留，无推送、部署、正式版本上传或远程迁移。API713项SQLite／760项真实MySQL回归，后台310项、小程序702项及静态／构建通过；最低schema0026／contract3，本轮无新迁移。

用户iPhone确认图片、实际倍速、PDF及返回、真实微信登录与主动收藏正常，追加的听读暂停／保持暂停／手动续播也已通过；Android及完整系统媒体／前后台／分享仍待实测。接续读[本轮验收](docs/verification/integration08-guest-20261107.md)、[379项状态](docs/verification/integration08-acceptance-index.json)、[配套提交](docs/handoff/revision17/repository-set.json)及[接口契约](docs/implementation/integration08-guest-contract.md)，下方历史发布授权不扩大本轮操作范围。

---

# 最新整合07测试发布与微信开发版（2026-11-06）

用户新增授权后，三仓已推远程test；测试双API／Worker／dispatcher及独立听读Worker共7服务和管理后台已部署，测试库备份后0026／contract3。固定API f219a39、后台97937db、小程序d99a12c。官方CI真实MySQL／Redis738通过／3跳过，双镜像通过；公网和契约复核通过，55原业务表原字段及行数保留，12个非目标容器元数据不变。

微信开发版本**1.5.0-test.20261106.184331**已上传，**体验版用户自行切换**，未提审或正式发布。仅部署测试，生产与原本地热更新保持。实际切换完成时间为北京时间22:31:12；见[发布记录](docs/verification/study-notes-test-release-20261106.md)与[无密钥回执](docs/verification/study-notes-test-release-20261106.json)。下方“仅本地／未部署”为此前开发阶段。

---

# 最新整合07学习笔记与列表分区（2026-11-06，仅本地）

本轮三仓现有test分支开发：API独立PDF版本／0026、后台PDF及ZIP核对、小程序双Tab与笔记来源队列已配套实现。最终功能头API ea6e0e4、后台97937db、小程序2cae38e。仅本地提交，未推送、部署、上传OSS／微信或迁移远程库；历史发布授权不扩大本轮范围。

API完整SQLite688通过／53条件跳过、独立MySQL737通过／4条件跳过，Redis定向1通过；后台310单测与6条相关浏览器、小程序625单测与双端本地构建通过，三仓静态检查通过。整体及定向复审六项发现全部关闭。微信iOS／Android、耳机／系统面板尚待真机，静态设计交付及完整Word核对不冒充程序通过。详见[逐条验收和兼容决定](docs/verification/study-notes-20261106.md)及[审查记录](docs/verification/study-notes-20261106-review.md)，接口见[契约](docs/implementation/study-notes-contract.md)。

当前实际本地5173／8291预览库备份、试升后0024→0026，55张原表原数据核对不变；旧0023接续库免费名单不明而保留，不猜测免费资格。预览worker跳过云TTS。远程环境未动。

---

# 最新管理后台与接口生产同步（2026-11-05）

用户授权将两个仓库 test 合并 release 并上线后，后台 c81aa8e 与双角色 API 固定运行版本 b2744ec 已完成生产发布。后台 286 测试、API 官方真实 MySQL/Redis CI 644 通过 / 3 跳过；7 服务 healthy，后台安装及公网资源哈希匹配，生产文档入口保持关闭。数据库仍 0025 / contract 3，无迁移或新增 ASR 调用；测试、基础设施及 CLI 保持。小程序本轮未再次上传，体验版由用户切换。见[发布与验收](docs/verification/admin-api-production-release-20261105.md)。下方为历史记录。

---

# 最新听读部分匹配高亮生产发布（2026-11-05）

用户授权上线后，固定源码 **13c2d4c** 的官方真实MySQL/Redis CI **633通过/3跳过** 及双镜像成功；生产管理API/配套Worker与dispatcher及独立听读Worker共4服务已原生发布且healthy。匹配词可高亮、遗漏词跳过；同输入复用已有识别任务，24小时过期结果拒绝重提。生产全部词轴、483个任务、0待执行及当日231次提交计数保持，无新增ASR提交。

《银行》原发布版保持ready/118词/revision2，无需重新发布文章；小程序无需重新上传。生产库仍0025/contract3，无迁移，其余15容器未变。详见[发布验收](docs/verification/listening-partial-production-release-20261105.md)和[无密钥回执](docs/verification/listening-partial-production-release-20261105.json)。下方“未发布”属于实施阶段历史。

---

# 最新数据库中文用途注释（2026-11-04）

测试及生产数据库已在线升级 **0025 / contract 3**：56张表390个字段中文注释完整，非注释结构保持，19个既有容器及应用版本指针不变，双环境四个公网ready200。源码a9e271b官方CI626通过/3跳过及双镜像成功；完整记录与备份摘要见[验收记录](docs/verification/database-comments-20261104.md)。最低schema仍0024，未发布或重启应用；本地SQLite的说明由模型保存，旧0023库保留。

---

# 最新生产发布与小程序1.0.0（2026-11-04）

按用户授权，四仓test全部并入release，生产双API/配套Worker与dispatcher及独立听读Worker共7服务、管理后台已发布并验收；CLI工作台原已是当前release并通过健康复核。数据库保持0024/contract3，无迁移；测试及基础设施其余12容器完整元数据不变。

微信生产包 **1.0.0**（manifest1.0.0/100）已通过官方CLI上传，API及静态资源均为生产域名，**体验版由用户自行切换**，未提交微信审核或发布正式版。六个压缩背景先行发布生产并核验。固定提交、自动化/实际浏览器验收与保留版本见[本轮发布记录](docs/verification/production-release-20261104.md)和[无密钥回执](docs/verification/production-release-20261104.json)。下方历史记录不代表当前生产状态。

---

# 最新列表性能测试 API 发布（2026-11-04，北京时间）

11-03 批次的测试 mini 三服务已于北京时间 **2026-11-04 00:05:34**（UTC 11-03 16:05:34）完成原生发布，固定源码 `00a4c1101b6413dd9a8d230f9cf82c8610464c45`，三容器 healthy。官方 CI 完整真实 MySQL/Redis **621通过/3跳过**，契约与镜像校验通过；公网 ready200、匿名听读列表401、mini域名admin auth路径404。测试库仍0024/contract3，无迁移，当前及上一版c690保留。

本次仅更新 `mini-api/mini-worker/mini-dispatcher`；测试 admin 三服务、独立 listening-worker、生产及其余16个容器ID/启动时间等保持。真实学习身份的首屏与音频端到端真机延迟仍待验。接续先读[发布及无秘密证据](docs/verification/loading-performance-test-release-20261103.md)和[三轮CI记录](docs/verification/listening-performance-test-ci-20261103.json)，下方“未部署”等实施阶段文字属于历史状态。

---

# 最新版本保留与服务器清理（2026-11-03）

按用户要求，测试/生产现用6个发布目标均只保留当前版及1个历史版，数据库/配置备份49份哈希不变，19容器未重启、14应用容器健康。发布CLI规则同步至`45ff9c0`，工作台已更新并改从release运行Actions。磁盘可用由约1GiB提升至12GiB，使用率69%。详见[清理记录](docs/verification/release-retention-20261103.md)。

---

# 最新生产 OSS 复验（2026-11-03）

用户确认授权后，生产juya桶对象写入/读取及11个私有静态资源上传、鉴权哈希核验完成。原不可达内网端点已修正，双API的实际ObjectStorage读写通过；7服务健康，测试及基础设施不变。公共ACL及删除仍受桶策略限制。微信生产包继续使用1.5.0-prod.1102.1及生产域名资源，未重复打包或切换体验版。详见[OSS复验记录](docs/verification/production-oss-verification-20261103.md)。

---

# 最新生产应用发布（2026-11-02）

四仓test已合并release，双API及Worker/dispatcher、独立听读Worker共7个生产服务、管理后台和发布工作台已部署。生产库从0018备份验证后升级0024/contract3，原记录保留。微信生产包`1.5.0-prod.1102.1`已上传，体验版由用户自行切换。生产公共静态素材已由生产API域名托管；生产OSS读写已于2026-11-03授权后复验通过，删除探测仍受限，详见后续记录。固定提交、修复、备份和验收见[生产发布记录](docs/verification/production-release-20261102.md)。

---

# 最新发音优化测试发布（2026-11-02）

用户新增授权后，正文发音预生成与小程序预加载已推送test并发布测试环境。双角色API/Worker/dispatcher及独立听读Worker共7服务为固定源码`c690358`且healthy，测试后台同步发布；微信`1.5.0-r17.06.1102.3`上传成功，体验版由用户手动切换。数据库保持0024/contract3，无迁移，生产环境保留；详情见[发布记录](docs/verification/word-audio-test-release-20261102.md)。下方为历史记录，不能将本地实施阶段“未部署”当作当前发布状态。

---

# 最新测试发布（2026-11-01）

用户新增授权后，整合06代码已推送远程 test，后台及双角色 API／Worker 已部署测试环境，测试库升级0024／contract3。微信包 1.5.0-r17.06.1101 上传成功，体验版由用户手动切换。固定提交、备份及实际核验见[发布记录](docs/verification/integration06-test-release-20261101.md)。下方“未部署”等表述是此前本地交付时的历史状态；本次未部署生产环境。原目录及本地热更新环境保留。

---

# 整合06／修订17本地接续（2026-11-01）

三端基于最新origin/test在`codex/revision17-integration06`隔离工作树增量开发。当前真源为整合06、T01—T321，设计62核心画板及18场景免费关联状态；旧主题层、数量N/M和全局免费排序退出当前流程。接续先读[本轮交付](docs/handoff/revision17/integration06/README.md)、[来源SHA](docs/handoff/revision17/requirement-reference.json)、[配套版本](docs/handoff/revision17/repository-set.json)。

最低schema0024、code contract3；升级前停写、备份并核对本机数据，旧免费名单/分类不明时preflight中止，不猜测、不自动扩权。0024不支持丢失新状态的downgrade；恢复须使用升级前核验备份。测试仅专用juya_verify/隔离SQLite，不能指向原业务库。

本轮原运行目录、私有配置、账号、媒体、业务数据保留，尚未切换到新工作树。没有合并、推送、部署、远程迁移或真实云调用。云词库/发音/ASR、真实微信身份与设备验收仍待办；本地构建、HTTP和合成身份结果不能当成这些验收。

下方整合05及更早授权/命令仅历史，不应用旧N/M或主题契约覆盖本轮。

---

# 整合05／修订17本地执行交接（2026-10-30）

当前需求已更新为V1.5整合05、T01—T300，设计为2026-10-30同步的55个当前画板及103个关联状态。执行在三个隔离工作树的`codex/revision17-integration05`，原运行目录、业务库、账号、配置与素材未覆盖。本轮没有推送、部署、远程迁移、OSS上传或真实云调用；下方旧交接的推送授权与环境命令属于历史记录。

先读[本轮实施与验收](docs/handoff/revision17/integration05/README.md)、[需求版本/SHA](docs/handoff/revision17/requirement-reference.json)及[配套版本](docs/handoff/revision17/repository-set.json)。最低schema仍为0023，本轮不新增迁移。自动化只使用临时SQLite及独立`juya_verify`，不能把清表夹具指向业务库。

---

## 2026-10-29冻结交接（历史）

# 修订17 MacBook增量接续交接

交接日期：2026-10-29（北京时间）。用户明确要求提交、推送各仓库远程 **`test`**，在另一台MacBook继续。**MacBook上的四个项目此前都已运行，本次是在已有环境上增量接续。** 当前仍只使用本地数据库；推送源码不包含部署或远程迁移授权。

本轮追加了修订17页面还原修复、主题英文名和后台只读发布预览；配套前端提交以[repository-set.json](docs/handoff/revision17/repository-set.json)为准。最低数据库版本0023，拉取源码不等于数据库已迁移；保留现有本地配置并先备份。

## 用户最新决定

- 保留Mac已有项目目录、运行配置、本地数据库和媒体、加密/lookup密钥、管理员与业务数据。
- 使用已有工具、容器和账号；按锁文件同步所需依赖，不重新初始化环境、建空库或创建管理员。
- 本次完整需求文档由用户另行同步到Mac，以用户同步的当前开发版为真源，不在Git重复存整份需求副本。版本和原文件SHA-256见[需求引用信息](docs/handoff/revision17/requirement-reference.json)。
- 本轮主要功能代码及R1—R7、契约UTF-8、S1批次更新补项已完成；真实云、设备及完整业务验收未完成。此前95%开发/85%可验收为工程估算，不是276条通过率。

## 四个现有仓库怎样更新

| 仓库                         | 目标分支 | 本轮变化                                                    |
| ---------------------------- | -------- | ----------------------------------------------------------- |
| `zhanjiangmrlu/juya-api`     | `test`   | 听读领域/接口/任务、0020—0023迁移、契约、测试及完整交接记录 |
| `zhanjiangmrlu/juya-admin`   | `test`   | 听读管理、导入恢复/更新、统计和复用播放器                   |
| `zhanjiangmrlu/juya-miniapp` | `test`   | 三Tab、主题听读、双类记录/收藏、进度与高亮                  |
| `zhanjiangmrlu/juya-cli`     | `test`   | 本轮无代码改动，保留现有发布工具                            |

分别进入Mac**已有的四个仓库目录**，先看`git status --short --branch`和`git log -1`。如有未提交修改，先自行提交/暂存保存；不要reset、清目录或强行覆盖。确认工作区已妥善保存后：

```zsh
git fetch origin
git switch test
git pull --ff-only origin test
```

如果不能快进或存在冲突，先检查双方提交，保留Mac已有工作；不要force pull/push。CLI没有本轮新提交，正常拉取其现有test即可。

两个前端与API必须一起更新，避免新客户端配旧契约。[本次配套版本](docs/handoff/revision17/repository-set.json)记录前端及CLI提交；API以包含该清单的test提交为准。依赖仍为Python3.13.x、Node22.22以上且小于23、pnpm11.25.0，继续使用Mac现有安装。按锁文件刷新依赖可复用现有缓存：API `uv sync --frozen`，前端各`pnpm install --frozen-lockfile`。不要升级依赖或锁文件。FFmpeg/FFprobe继续沿用原Mac路径。

## 需求、设计与实施证据

用户将同步`句芽英语-开发需求交接版-当前开发版.md`：V1.5整合04增补02、CHG-0027、修订17增补02、T01—T276。原Windows工作区约定它在API仓库相对`../../docs/需求文档/`；Mac实际路径以用户同步位置为准。若原文件哈希不同，先核对版本和业务变更，不能拿旧文档覆盖用户的新需求。

- [实施与验收决定](docs/handoff/revision17/source/开发方案/修订17-实施与验收.md)、[后端契约](docs/handoff/revision17/source/开发方案/修订17-后端契约.md)。
- [本地交付说明](docs/handoff/revision17/source/开发方案/修订17-本地交付说明.md)、[审查修复报告](docs/handoff/revision17/source/开发方案/修订17-审查修复报告.md)、[最终复审](docs/handoff/revision17/source/开发方案/修订17-修复复审.md)。
- [276条追踪](docs/handoff/revision17/source/开发方案/修订17-验收追踪.json)、[9张实际运行截图](docs/handoff/revision17/source/开发方案/验收截图/修订17)。
- Figma：[当前设计导航](https://www.figma.com/design/yVnE9TCSoRS5sv4vAuxsBX/Juya?node-id=48-5107)、[逐字/暂停状态](https://www.figma.com/design/yVnE9TCSoRS5sv4vAuxsBX/Juya?node-id=64-5079)、[53个具体画板](docs/handoff/revision17/source/开发方案/修订17-设计验收清单.md)。

`source`中的报告是Windows实施阶段冻结证据；“未提交/未推送”、Windows绝对路径和`.private`日志是当时状态，不是Mac当前状态。报告中的私密runner不随Git同步。后续在这套仓库内交接记录上继续登记新验证和决定，不重建多份方案。

## Mac本地库只做增量迁移

本次代码head为**0023**：0020新增13张听读表，0021隔离未发布主题改动，0022增加分类英文名和主题简介；0023兼容新增主题英文名（默认空串），不改写中文名、简介、账号、学习事实或媒体。Mac当前版本以实际库为准，仍须先备份并核验目标，再按以下流程增量升级。

1. 核对Mac现有API配置确实连接本地库。分支名test不意味着使用远程测试数据库；本地数据库名和端口沿用Mac原配置，不改成Windows的13306/juya_local示例。
2. 先暂停本地API、旧worker和dispatcher写入，使用Mac已有备份方式备份**当前本地库**并确认备份可恢复，同时保留原媒体和加密配置。不要拿Windows较早0013/0020备份覆盖Mac现有数据。
3. 从API仓库执行下列片段：使用现有Settings读取配置，验证应用和迁移均指向同一个本地库，再显示当前版本并升级。不要运行downgrade、drop/create_all或测试清表夹具。

```zsh
uv run python - <<'PY'
import os
from sqlalchemy.engine import make_url
from alembic import command
from alembic.config import Config
from juya_api.config import Settings

settings = Settings()
application = make_url(settings.database_url)
migration_url = os.environ.get('JUYA_MIGRATION_DATABASE_URL') or settings.database_url
migration = make_url(migration_url)
local_hosts = {'127.0.0.1', 'localhost', '::1'}
assert settings.environment == 'local', 'Inspect the existing local environment configuration first'
assert application.host in local_hosts and migration.host in local_hosts
assert application.drivername.startswith('mysql') and migration.drivername.startswith('mysql')
assert application.database and application.database not in {'juya_verify', 'mysql', 'sys', 'information_schema', 'performance_schema'}, 'Use the existing business database'
normalize_host = lambda host: '127.0.0.1' if host == 'localhost' else host
assert (normalize_host(application.host), application.port or 3306, application.database) == (normalize_host(migration.host), migration.port or 3306, migration.database), 'Application and migration must target the same local database'
os.environ['JUYA_DATABASE_URL'] = settings.database_url
config = Config('alembic.ini')
command.current(config)
command.upgrade(config, 'head')
PY
```

`migrations/env.py`不自行载入.env，所以这里先调用Settings再传给Alembic。若你的原环境通过本地容器网关而不是loopback访问MySQL，先核对确实是Mac本机数据库，再按实际本地地址调整校验；不要直接删除校验连接远程。若现有schema不属于当前test迁移历史，先调查分支和版本，不强制降级。

本地HTTP仍需`JUYA_COOKIE_SECURE=false`；`JUYA_ALLOWED_ORIGINS`应包含Mac实际后台来源。现有密钥不要重生成。若需使用当前统一授权配置入口，核对本地`JUYA_LEARNING_ACCESS_ACTIVATION_READY=true`，不更改任何远程开关。两API和worker沿用同一配置、相同实际媒体目录；`JUYA_STORAGE_BACKEND=local`用于本轮本地素材。

## 重启已有进程及新增听读worker

本机端口沿用原约定（如Mac原来不同，使用原配置并同步前端代理）；下列为代码默认本地端口，各进程独立终端，从同一个API仓库目录运行：

```zsh
uv run uvicorn juya_api.admin:create_app --factory --host 127.0.0.1 --port 8001 --no-access-log
```

```zsh
uv run uvicorn juya_api.mini:create_app --factory --host 127.0.0.1 --port 8002 --no-access-log
```

旧场景异步处理沿用原角色worker/dispatcher配置，实际入口仍为`juya_api.worker_main --pool solo`及`juya_api.dispatch`（角色`JUYA_WORKER_ROLE=admin|mini`）。**本次增加的独立听读worker不能省略，也不能由旧worker替代：**

```zsh
JUYA_ASR_SECRET_ID='' JUYA_ASR_SECRET_KEY='' uv run python -m juya_api.listening_worker
```

上例显式关闭云ASR。没有权限/配置时时间轴失败并正常听读降级；真实云验收时再明确接通。原MySQL、Redis、媒体及管理员继续使用，不初始化新账号。重启后检查两角色`/health/ready`为HTTP200且`environment=local`，再用原本地管理员登录。

## 前端与微信工具接续

后台在已有`juya-admin`目录运行：

```zsh
VITE_API_BASE_URL='' VITE_DEV_API_PROXY_TARGET=http://127.0.0.1:8001 pnpm dev
```

默认`http://127.0.0.1:5173`。当前听读分类/主题、两种排序、免费M、草稿/发布、导入恢复/更新、删除和统计均使用真实本地API。不要为了预览而自动重置已有免费配置或发布内容。

小程序H5在已有`juya-miniapp`目录运行：

```zsh
VITE_API_BASE_URL='' VITE_DEV_API_PROXY_TARGET=http://127.0.0.1:8002 VITE_STATIC_ASSET_BASE_URL='' VITE_REMOTE_FONTS=false pnpm dev:h5
```

默认`http://127.0.0.1:5174`。微信开发者工具包另开终端构建：

```zsh
VITE_API_BASE_URL=http://127.0.0.1:8002 VITE_STATIC_ASSET_BASE_URL='' VITE_REMOTE_FONTS=false pnpm build:mp-weixin:test
```

导入或重新打开`dist/build/mp-weixin`，沿用Mac原AppID和工具配置。H5空API前缀不能用于原生请求；版本化.env中远程API地址不能当成本地地址。127.0.0.1仅适用于Mac本机工具，手机真机按现有可访问地址/合法域名配置。源码拉取不会迁移Windows合成身份或登录Token，真实微信身份仍须实际验证。

## 提交前验证与后续待办

本次新鲜检查见[推送前验证记录](docs/handoff/revision17/pre-push-verification.md)：API完整SQLite **471通过/32跳过/15既有Windows平台失败**；后台完整**188**，小程序完整**383**，静态检查和构建通过。旧完整460/31/15、S1专项50/4、MySQL分批及浏览器均按各自范围记录，不能相加。所有Mac命令按真实入口核对，但这次未在Mac实跑，不能据此推断Mac平台检查已绿。

接续时优先：

1. 保存Mac现有工作，四仓更新test；备份并增量迁移原本地库，重启双API和独立听读worker，核对原数据保留和新功能可用。
2. 先复验后台新建/导入/更新原文章：选择目标和revision、核对差异、确认才更新原草稿；原发布版、收藏完成历史保持，同资料及同媒体不同上传ID应跳过。
3. 接通有授权词库/单词TTS。未配置词库时通用词典真实返回dictionary_unavailable，不可当成已接入。
4. 核对腾讯ASR权限。Windows真实TTS成功，但ASR返回AuthFailure.UnauthorizedOperation，真实录音时间轴和同步未验；开通后验证独立持久任务、词偏移、尾迹与暂停效果。
5. 微信真实身份/真机、图片手势、到期权限、长队列来源、系统回收恢复，再按用户同步需求的276条及53画板登记验收和必要修正。

API常规检查为`uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy src`及`uv run pytest -q`。普通测试默认SQLite；真实MySQL只能使用专用**juya_verify**，夹具会清库，Redis用独立DB15。不得把测试URL指向Mac原业务库。两前端各`pnpm check`，后台`pnpm test`/`pnpm build`，Mini `pnpm test --maxWorkers=2`/H5/上述本地微信构建。

契约仍由API `uv run python scripts/export-openapi.py`导出UTF-8/LF，复制admin/mini JSON到对应前端，再各`pnpm generate:api`；不要手改生成类型。推送test会触发API现有CI/打包，配置没有自动部署步骤；两个前端main-only质量工作流不会因push test运行。不要预先声称CI通过。

Git本次不包含Windows数据库、媒体、账号、.env、.private、Token或依赖缓存；Mac继续使用自己已有的对应资料。不要复制Windows虚拟环境、缓存或旧密钥覆盖Mac。后续先读仓库AGENTS、本文件、用户同步的需求及最终复审，不重做已完成模块，也不把源码推送视为部署授权。
