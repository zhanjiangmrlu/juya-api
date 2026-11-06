# 整合07 学习笔记与列表分区实施计划

用户于2026-11-06批准方案并指定在三仓test分支开发。需求真源：/Users/lubi/Desktop/juya/句芽英语-整合07-学习笔记PDF与列表分区-增量需求-20261106.docx，Figma yVnE9TCSoRS5sv4vAuxsBX 节点254:4988。

## Global Constraints
- 只在现有三仓test开发，不推送、部署、OSS上传、微信上传或远程迁移。保留本地配置、账号、业务数据。自动测试只用隔离数据库。
- 单文件PDF默认20*1024*1024字节，服务端可配置并展示实际限制。
- 更新旧卡时ZIP缺少PDF保留原笔记；明确不添加/移除，发布后才解除关联。
- PDF独立附件版本，发布事务与正文共同确认。仅改PDF不变正文CardVersion、音频、阅读位置、排序、收藏、成绩、打卡，不触发TTS。
- 无PDF旧数据/旧ZIP完全兼容。待选择、校验中、失败的PDF可存草稿，但发布必须就绪或明确取消。
- 所有资源请求重验当前发布、免费/授权、会话、附件版本；不提供永久公开URL。管理员查看不写学习数据。
- 前端按各仓AGENTS规范：SCSS嵌套、script setup、const箭头函数、函数注释、kebab-case、测试放tests；后台通用控件ElementPlus优先。
- 提交标题type(scope): 中文说明；不改写历史。

## Task 1: 后端闭环
在juya-api实现独立CardStudyNoteVersion及当前引用；CardDraft/ImportItem保存有效/待处理附件与保留/设置/移除/未决决策。迁移接当前0025（核实head），新代码最低schema随新增结构更新，扩展兼容contract3；新增中文表字段注释。
复用Media/ObjectStorage/media.decode、状态/重试/幂等收据；PDF校验用pypdf实际格式、页结构、内容、加密可读性及20MB限制。上传完成不是ready，失败不覆盖旧有效引用。候选/发布预览分别对应资源，指纹包含笔记，发布原子切换；note-only保持正文版本和排序但更新目录版本。
ZIP按包实例parent_id+目录隔离，唯一自动关联，多份选择或不添加，异常替换/移除，部分成功不重复保存。导入去重包含笔记内容及动作，卡片身份沿用现有。
扩展现有GET /api/mini/v1/cards：scope=uncompleted|published，has_study_note可选bool；默认待学，notes用published+true。数据库筛选count排序后分页，越界回有效页。安全摘要仅has_study_note，受限不泄露filename/mediaID/URL；详情获权后提供study_note元数据及独立版本。下载票据purpose=study_note并绑定note版本，每次GET/HEAD/Range复验。
QueueSource增加learning_notes，包含已学，当前资格重验有效PDF；learning来源无PDF仍合法。固定索引快照不循环、不跨来源，notes结束不套用free_uncompleted判断。
输出docs/implementation/study-notes-contract.md，明确真实新增接口字段，供两端实现；导出openapi。先RED后GREEN，覆盖T322—T355中服务端部分及MySQL并发、旧票据、发布回滚、导入隔离/旧包保留。运行ruff/mypy/pytest和可用隔离MySQL，不能访问真实业务库。

## Task 2: 管理后台
根据Task1实际契约同步openapi/generated。独立笔记组件提供上传查看替换移除、真实状态、失败保留旧文件、取消更换拒绝迟到绑定，未知收据恢复与原幂等逻辑。待处理PDF可存草稿，发布须处理/取消。候选与发布预览各取正确附件，管理员Blob查看，释放URL，不调用mini接口。
ZIP核对同目录唯一自动、多选明确、不添加/移除、损坏修正；未提供保留原笔记；失败不拖其他卡片；帮助模板仅场景ZIP。
Figma后台节点232:4797/232:4958/233:4812/233:5006，手机入口231:4787。优先El组件且沿用既有风格。TDD+pnpm check/test/build和相关e2e。

## Task 3: 小程序
同步Task1契约。学习列表统计下增加全部场景/含学习笔记两个自然宽Tab，32px间距、2px绿下划线1px浅基线、>=44px点击区。全部待学不限PDF；notes所有有效发布PDF含已学。独立分页快照错误，失败不假0，空态按原文。已学/可复习独立展示；统计历史口径不变。
详情入口文档图标+#41664D/13px Medium无框底，>=44px；无PDF不占位，长标题完整换行入口独立右对齐。单飞重新验权/附件=>暂停所有音频并取消在途=>downloadFile=>openDocument pdf。mark_started=false刷新不记录开始；重试重验；临时文件按账号卡片笔记版本隔离，不复用旧权限文件。下载/打开错误分开原位重试。原生文档期间抑制耳机/迟到播放，返回保存滚动译文进度倍速，手动续播，不能onHide销毁或onShow自动播放。登录承接目标笔记动作。
来源learning_notes，下一张仅本来源实时合法队列，已学notes不跳过；PDF移除仅影响notes源。返回原Tab与位置，主动换Tab到顶部，首页新进入默认全部；队列空返回对应Tab刷新，无栈重建来源。
Figma列表45:4984/249:5098/250:4985/250:5057，详情231:4787/231:4874/231:4956。原背景字体/首页/音频控件不改。
TDD+pnpm check/test及隔离H5/微信local构建，不使用自动OSS同步发布命令。

## Task 4: 全量审查验收
逐条追踪T322—T355，区分自动化/浏览器/真机/未验；设计证据338/339/354/355不冒充程序通过。运行三仓完整测试与静态检查，浏览器验证后台真实流程；微信iOS/Android真机不可用时如实待验。新鲜独立审查并修复重要问题，更新HANDOFF/progress、配套版本记录。不推送、不发布。

## 实施补充裁定

- `study_note`省略或null保留当前决策，只有`action: remove`明确移除；实际容量字段为`study_note_limit_bytes`。
- 增加可选`previous_media_id`，一次保存尚未持久化的有效附件与待处理替换，服务端同时校验ready、归属和ZIP来源；完整约束见实际接口契约。
- 详情GET兼容新增默认false的`require_study_note`：笔记正文准入使用true，锁内先验当前PDF和权限、再记录原有ReadingStart；纯PDF意图保持`mark_started=false`。避免以全部关闭开始记录规避失效候选竞态。
- 当前预览库备份后增量升级0026；旧0023接续库因既有免费名单核对阻断而保留，不猜测免费资格。详见验收记录。
