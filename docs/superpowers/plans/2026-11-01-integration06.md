# 整合06 · 修订17三端实施计划

用户于2026-11-01批准聊天中的完整计划。业务真源：`/Users/lubi/Desktop/juya/句芽英语-原型与Figma-整合06同步版-20261031-修订17/句芽英语V1.5完整需求文档-当前确认版.md`；设计状态以同目录“本次同步说明.txt”和“页面同步清单.md”为准。原正文待同步描述已由2026-11-01执行记录替代。

## Global Constraints

- 仅本地三端开发与验证；云词库/发音/ASR和微信真机单列待验；不部署、不推送、不远程迁移、不清理业务数据
- 三仓使用隔离工作树 `/Users/lubi/Desktop/juya/.worktrees/revision17-integration06/{juya-api,juya-admin,juya-miniapp}`，基线最新origin/test
- 保留稳定内容、版本、媒体、时间轴、收藏、完成、进度及导入批次身份；只改分类/顺序/免费设置不生成内容版本
- 免费有效集合为指定开启且有效发布未删除，默认关闭；无数量门槛，无授权仍不能正文查词
- 后台新增/重做控件采用Element Plus；Vue3 script setup、SCSS嵌套、const箭头函数及参数业务注释，文件命名遵循各仓AGENTS
- 自动化MySQL只用本地专用juya_verify；运行配置和凭据不入Git；提交为type(scope): 中文说明

### Task 1: API、迁移与共享契约

Worktree: juya-api。完成CHG0032—0035后端全部行为及回归，先行为测试RED再实现GREEN，最后完整pytest/ruff/mypy；导出OpenAPI供两前端生成类型。

- schema0023上增量迁移：分类直接归属和分类内篇序，保留草稿/发布归属，topic历史字段可空且不创建虚拟主题；分类soft-delete保留历史FK；分类删除校验全部未删除文章的两种引用，含并发
- 升级前固化两类旧有效免费ID；增加各对象is_free与独立free_revision，审计稳定引用、前后状态、管理员时间。只本地安全迁移；不明旧集合/坏分类中止，不猜。新增/导入false，下线保留、删除不可复活不补位；旧N/M/global free order写接口410
- 新鉴权有效发布&&(is_free||active grant)，点词必须active；复用事务锁序、operate幂等、receipt、权限epoch，GET/HEAD/Range旧资源票据重验。新增管理员 `/cards/{id}/free-access` 与 `/listening/articles/{id}/free-access` GET/PUT，PUT `{is_free:boolean,revision:int}`，返回 `{is_free,revision,effective}`，revision为free_revision；全量免费汇总只读
- Article/Candidate/Summary/Home等以category_id/category_order/category_name为新契约；mini `/listening/articles?category_id=&page=` 直接分页，分类进度和独立continue；category内order替代topic/global，旧topic read只作所属category映射；旧topic写停用
- 单改归属发布复用原version_id和timeline hash，实质payload变化才生成新version；比较时将旧缺省vocabulary和空数组视为同义，不改不可变历史payload
- ListeningPayload `vocabulary=[]`：稳定id、english、meaning、phonetic、source（当前body Unicode code point原句范围/quote、目标词范围及明确词形对应）；多义分条不按拼写覆盖；修改正文后重查来源。有词校验，空词可发布，5表达仍独立必填。词汇不计正文词数/时间轴输入
- 预置词汇发音复用pronunciation缓存/任务，按article+version+wordID服务端取词；新增两角色 `/listening/articles/{id}/words/{word_id}/pronunciation` GET/POST，mini需要can_learn而非can_lookup；admin预览/导入核对试听不写学习成绩。票据交付重验角色/会话/当前访问/版本与词条，任意正文查词原接口保持can_lookup
- 新模板去主题必填，选填词汇H2四列词汇/本句释义/音标/对应英文原句；兼容旧无词/含主题，分类精确唯一匹配。来源多处/词形需核对。候选更新/恢复/发布草稿双出口/重复/失败重试/未知先查保持
- 去重：空词汇canonical剔除空数组用旧v1；有词汇版本化v2含词汇语义和顺序、排随机id/确认状态。保留原source_hash及已成功receipt；未成功候选迁移映射后bump batch revision使旧token失效，保留ID/目标绑定/成功项

Deliverable: 测试和迁移、openapi/admin.json及mini.json、中文提交；报告在本计划工作区task-1-report.md，另写精确前端契约 task-1-interfaces.md，注明实际URL、参数、DTO、分页和兼容行为。

### Task 2: Element Plus后台

Worktree: juya-admin。读取task-1-interfaces.md及生成契约，新增控件使用Element Plus，复用项目token；独立组件避免堆大文件。原生手写既有无关部分不全站重构。

- 两个Tab文章/分类；移除主题/免费数量/全局免费排序入口，旧路由重定向；分类增改排序和当前页删、引用阻删；分类内文章排序
- 场景/文章逐行free-access，独立pending/失败/未知查询/幂等，按钮不隐含其他勾选项；成功刷新真实状态及全量只读汇总，保留筛选分页滚动
- 文章选择有效分类；完整词汇增删排序、来源句选择/词形对应、校验、受控试听；空词隐藏预览仍可发布；草稿/发布版归属正确
- DOCX帮助/模板/解析核对一致；旧包兼容，词汇数/问题显示，来源核对；批次恢复、目标更新、fingerprint/revision、成功不重做/只重试失败保留
- 复用Figma当前画板，必须先读figma-design-to-code技能，按小节点get_design_context+截图取高保真；素材复用精确匹配或按工具要求下载。Figma sessionId a4718984-5649-41ef-86d8-562313eee61c/fileKey yVnE9TCSoRS5sv4vAuxsBX，Primary link_6ac75f86ffd0819189ba183e9371c574
- 行为测试RED→GREEN，pnpm check/test/build，报告task-2-report.md，中文提交

### Task 3: 小程序

Worktree: juya-miniapp。读取task-1-interfaces.md和生成契约，遵循AGENTS类型/常量/组件与tests目录规则，复用资源/音频控制器/列表来源机制。

- 首页雅思词汇/IELTS Vocabulary/结合场景图片和日常对话，积累约3,700个词汇。/开始学习；主题听读三行English in Real Life：涵盖10类日常英语内容。IELTS Speaking B2–C1：涵盖10类口语内容。生活场景听读：约覆盖1.5万—2万词汇。按钮开始听读；数字固定介绍，不全局改场景业务名
- 分类直接文章：全部按分类序+篇序，分类进度/限制摘要/缩略图，64px分类按钮、44px触区、三列最高65%面板，名称长/2/10/超过10分类均工作，分类过滤/分页返回位置保留。旧topic页redirect所属分类
- continue与筛选独立；next只同类向后不回绕，末篇返所属分类，收藏/记录辅助名改分类；版本内阅读、译文、进度、倍速保留
- 词汇区译文之后5表达之前，有词展示20px英文音标/16px释义原句，无词全隐藏；仅预置单词发音，暂停全文与高亮尾迹、切词中止旧发音/异步请求、防叠播、失败原位重试，手动续播/离开停音
- 权限进入/回前台/动作/到期/30秒周期复核，收到失效即停受限资源；免费保留预置词音，仅正文查词需要授权，失败不假免费
- 高保真Figma按task2同会话小节点读取；确认水彩背景/字体/图标沿用，新增真实3x资源外置兼容OSS，微信包预算校验
- 行为测试RED→GREEN，pnpm check/test/H5及显式本地微信构建，报告task-3-report.md，中文提交

### Task 4: 本地联调、视觉与交付

Worktree: 三端。只用隔离本地SQLite/专用MySQL juya_verify及本地媒体，既有业务环境不切换。

- 真实HTTP后台模板导入→分类/词汇来源核对→发布→逐项免费→用户全文/词汇发音→关闭免费→旧票据GET/HEAD/Range拒绝；发音样本仅测试侧，产品不增加绕过
- SQLite全套和真实MySQL迁移/锁约束/并发幂等，前端check/test/build和小程序微信分包预算
- 62核心+18场景free状态逐项追踪；375/390手机、1440/960后台截图比对，复用已确认资产；记录实际验到范围，不以静态测试代替视觉/真机
- 更新HANDOFF/requirement-reference/repository-set/traceability/progress及证据；真实云/ASR/微信设备明确待验，不宣称全通过

## Review Focus

旧N/M权限迁移不能扩大；仅分类改变不能重置进度；旧导入空字段不能击穿去重；预置词汇发音不能绕任意查词授权；未知提交不能重复写入/锁死页面。
