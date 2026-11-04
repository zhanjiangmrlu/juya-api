"""Document tables and columns without changing business data or the code contract."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.schema import CreateColumn

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

# Frozen at revision 0025: historical migrations must not import runtime models.
COMMENTS = {
    "admin_action_batches": {
        "table": "管理员批量下架或删除操作批次",
        "columns": {
            "id": "记录内部标识",
            "admin_id": "操作管理员标识，关联administrators.id",
            "action": "批量操作：offline下架或delete删除",
            "created_at": "创建时间（UTC，微秒精度）",
        },
    },
    "admin_action_items": {
        "table": "批量下架或删除操作的场景快照和逐项回执",
        "columns": {
            "id": "记录内部标识",
            "batch_id": "所属管理员批量操作标识，关联admin_action_batches.id",
            "card_id": "操作目标场景稳定标识，删除后保留回执",
            "name": "操作确认时的场景中文名称快照",
            "title_en": "场景英文标题快照",
            "revision": "操作确认绑定的场景草稿版本号",
            "status": "确认时场景状态：draft、published、offline、deleted或missing",
            "version_id": "关联不可变发布版本标识",
            "job_id": "关联异步处理任务标识；空表示尚无任务",
            "skip_reason": "跳过该场景的业务原因；空表示未跳过",
            "position": "项目在所属列表中的顺序位置",
        },
    },
    "admin_media_sources": {
        "table": "管理员上传媒体的原始文件名",
        "columns": {
            "media_id": "关联媒体标识，关联media.id",
            "original_name": "管理员上传时的原始文件名",
        },
    },
    "admin_sessions": {
        "table": "管理后台登录会话与CSRF凭据",
        "columns": {
            "token_digest": "会话或访问令牌的SHA-256摘要，不保存令牌原文",
            "admin_id": "操作管理员标识，关联administrators.id",
            "csrf_digest": "CSRF令牌的SHA-256摘要，用于请求校验",
            "csrf_cipher": "可恢复的CSRF令牌Fernet密文",
            "expires_at": "过期时间（UTC，微秒精度）",
        },
    },
    "administrators": {
        "table": "管理后台管理员账号",
        "columns": {
            "id": "记录内部标识",
            "username": "管理员登录用户名，库内唯一",
            "password_hash": "管理员密码的Argon2哈希，不保存密码原文",
        },
    },
    "audits": {
        "table": "管理员业务操作审计记录",
        "columns": {
            "id": "记录内部标识",
            "admin_id": "操作管理员标识，关联administrators.id",
            "action": "执行的业务操作名称",
            "object_id": "被操作业务对象标识；空表示无单一目标对象",
            "occurred_at": "操作发生时间（UTC，微秒精度）",
        },
    },
    "card_drafts": {
        "table": "场景当前可编辑草稿",
        "columns": {
            "card_id": "场景稳定标识，关联cards.id",
            "revision": "并发修改校验版本号",
            "payload": "场景当前草稿内容JSON，包含中英文资料、词汇及媒体引用",
            "updated_at": "最近更新时间（UTC，微秒精度）",
        },
    },
    "card_versions": {
        "table": "场景不可变已发布版本",
        "columns": {
            "id": "记录内部标识",
            "card_id": "场景稳定标识，关联cards.id",
            "number": "同一场景内递增的发布版本序号",
            "payload": "场景不可变发布内容JSON，包含中英文资料、词汇及媒体引用",
            "content_hash": "规范化内容的SHA-256摘要，用于校验内容一致性",
            "published_at": "版本发布时间（UTC，微秒精度）",
        },
    },
    "cards": {
        "table": "雅思词汇场景的稳定身份与发布状态",
        "columns": {
            "id": "记录内部标识",
            "status": "场景状态：draft草稿、published已发布、offline已下架",
            "is_free": "是否对未获学习授权用户免费开放（0否，1是）",
            "free_revision": "当前免费资格的并发校验版本号",
            "current_version_id": "当前已发布场景版本标识；空表示从未发布",
            "sort_order": "排序值，按升序展示",
            "created_at": "创建时间（UTC，微秒精度）",
            "deleted_at": "软删除时间（UTC，微秒精度）；空表示未删除",
        },
    },
    "checkins": {
        "table": "用户按北京时间自然日记录的学习打卡",
        "columns": {
            "user_id": "所属用户内部标识，关联users.id",
            "date": "学习事实所属北京时间自然日",
            "accepted_at": "服务端接受操作时间（UTC，微秒精度）",
        },
    },
    "completions": {
        "table": "用户场景首次和最近完成事实",
        "columns": {
            "user_id": "所属用户内部标识，关联users.id",
            "card_id": "场景稳定标识，关联cards.id",
            "first_completed_at": "首次完成时间（UTC，微秒精度）",
            "last_completed_at": "最近完成时间（UTC，微秒精度）",
            "first_version_id": "首次完成时的不可变发布版本标识",
            "last_version_id": "最近完成时的不可变发布版本标识",
            "safe_name": "首次完成时保存的安全场景名称快照，供历史记录展示",
            "thumbnail_id": "缩略图媒体标识；空表示无缩略图",
        },
    },
    "consents": {
        "table": "用户协议和隐私授权同意记录",
        "columns": {
            "id": "记录内部标识",
            "user_id": "所属用户内部标识，关联users.id",
            "purpose": "用户同意的授权或协议用途",
            "version": "用户接受的协议版本标识",
            "accepted_at": "服务端接受操作时间（UTC，微秒精度）",
        },
    },
    "content_migration_snapshots": {
        "table": "内容结构迁移前的持久快照，用于中断续迁",
        "columns": {
            "id": "生成快照的结构迁移版本标识",
            "payload": "升级前源数据及确定性映射的冻结JSON快照",
        },
    },
    "daily_learning": {
        "table": "按北京时间自然日记录的场景学习事实",
        "columns": {
            "user_id": "所属用户内部标识，关联users.id",
            "card_id": "场景稳定标识，关联cards.id",
            "date": "学习事实所属北京时间自然日",
            "accepted_at": "服务端接受操作时间（UTC，微秒精度）",
            "version_id": "关联不可变发布版本标识",
        },
    },
    "favorites": {
        "table": "用户场景收藏关系",
        "columns": {
            "user_id": "所属用户内部标识，关联users.id",
            "card_id": "场景稳定标识，关联cards.id",
            "created_at": "创建时间（UTC，微秒精度）",
        },
    },
    "feedback_events": {
        "table": "反馈线程内追加事件及加密消息",
        "columns": {
            "feedback_id": "所属反馈线程标识，关联feedbacks.id",
            "id": "线程内按服务端顺序递增的事件序号",
            "actor": "事件发起角色：user用户或admin管理员",
            "actor_id": "事件发起用户或管理员的内部标识",
            "text_cipher": "反馈消息Fernet密文；仅状态变更时可为空",
            "status": "该事件设置的新反馈处理状态；未变更状态时为空",
            "created_at": "创建时间（UTC，微秒精度）",
        },
    },
    "feedback_images": {
        "table": "反馈图片及所关联的消息事件",
        "columns": {
            "id": "记录内部标识",
            "user_id": "所属用户内部标识，关联users.id",
            "feedback_id": "绑定的反馈线程标识；尚未提交时为空",
            "event_id": "绑定的反馈消息事件序号；尚未提交时为空",
            "event_position": "图片在同一反馈消息内的展示位置",
            "storage_key": "私有存储对象键",
            "content_type": "媒体MIME类型",
            "sha256": "文件原始字节的SHA-256摘要",
            "size": "文件大小（字节）",
            "width": "图片宽度（像素）；空表示不适用",
            "height": "图片高度（像素）；空表示不适用",
            "created_at": "创建时间（UTC，微秒精度）",
        },
    },
    "feedback_reads": {
        "table": "反馈参与者的已读事件水位",
        "columns": {
            "feedback_id": "所属反馈线程标识，关联feedbacks.id",
            "role": "阅读者角色：mini小程序用户或admin管理员",
            "actor_id": "阅读者用户或管理员内部标识",
            "event_id": "该阅读者已读到的最大线程事件序号",
        },
    },
    "feedbacks": {
        "table": "用户反馈主线程及加密摘要",
        "columns": {
            "id": "记录内部标识",
            "user_id": "所属用户内部标识，关联users.id",
            "category": "反馈类别：content内容、pronunciation发音、display显示、function功能",
            "status": "处理状态：pending待处理、processing处理中、needs_info待补充、resolved已解决",
            "summary_cipher": "反馈摘要Fernet密文",
            "source": "反馈入口：profile账号页或scene场景页",
            "card_id": "反馈关联场景标识；账号页反馈可为空",
            "version_id": "反馈发生时的场景发布版本标识；可为空",
            "source_title": "反馈来源的中文场景标题快照",
            "source_title_en": "反馈来源的英文场景标题快照",
            "latest_event_id": "线程最近事件序号",
            "latest_user_event_id": "最近一条用户事件序号",
            "latest_admin_event_id": "最近一条管理员事件序号",
            "created_at": "创建时间（UTC，微秒精度）",
            "updated_at": "最近更新时间（UTC，微秒精度）",
        },
    },
    "import_batches": {
        "table": "场景资料导入批次与软删除状态",
        "columns": {
            "id": "记录内部标识",
            "admin_id": "操作管理员标识，关联administrators.id",
            "mode": "场景导入模式：zip压缩包、docx文档、single单卡文档",
            "created_at": "创建时间（UTC，微秒精度）",
            "updated_at": "导入批次最近活动时间（UTC，微秒精度）；旧记录可为空",
            "deleted_at": "软删除时间（UTC，微秒精度）；空表示未删除",
        },
    },
    "import_files": {
        "table": "导入源文件、处理任务及进度",
        "columns": {
            "id": "记录内部标识",
            "batch_id": "所属场景导入批次标识，关联import_batches.id",
            "parent_id": "父级导入文件标识；空串表示顶层文件",
            "name": "导入文件名或包内相对路径",
            "kind": "导入文件类型，用于选择解析或媒体处理流程",
            "storage_key": "私有存储对象键",
            "size": "文件大小（字节）",
            "sha256": "文件原始字节的SHA-256摘要",
            "media_id": "关联媒体标识，关联media.id",
            "job_id": "关联异步处理任务标识；空表示尚无任务",
            "error_code": "最近处理错误的业务代码；空表示无错误",
            "progress": "文件解析阶段及进度JSON快照",
            "created_at": "创建时间（UTC，微秒精度）",
        },
    },
    "import_identities": {
        "table": "场景导入去重身份及最近保存版本",
        "columns": {
            "object_key": "跨批次复用的导入对象身份摘要",
            "card_id": "场景稳定标识，关联cards.id",
            "content_hash": "规范化内容的SHA-256摘要，用于校验内容一致性",
            "draft_revision": "最近保存到目标场景的草稿版本号",
        },
    },
    "import_items": {
        "table": "场景导入候选内容与逐项保存结果",
        "columns": {
            "id": "记录内部标识",
            "batch_id": "所属场景导入批次标识，关联import_batches.id",
            "source_file_id": "生成候选项的源文件标识，关联import_files.id",
            "source_index": "候选项在源文件内的位置编号",
            "source_identity": "候选项的稳定来源身份摘要",
            "content": "候选场景草稿内容JSON",
            "parser_issues": "解析和内容校验问题JSON列表",
            "readable": "源内容是否可读（0否，1是）",
            "selected": "候选项是否选中保存（0否，1是）",
            "revision": "并发修改校验版本号",
            "target_card_id": "明确选定的更新目标场景；空表示新建",
            "target_revision": "更新目标场景的确认草稿版本号",
            "saved_card_id": "最近成功保存的场景标识",
            "saved_draft_revision": "最近成功保存后的场景草稿版本号",
            "last_saved_hash": "最近成功保存内容的摘要，用于跳过重复保存",
            "job_id": "关联异步处理任务标识；空表示尚无任务",
            "position": "项目在所属列表中的顺序位置",
        },
    },
    "jobs": {
        "table": "场景和发音等通用持久任务、重试及工作租约",
        "columns": {
            "id": "记录内部标识",
            "kind": "异步任务类型，如import.parse、import.save、media.decode或发音合成",
            "owner_kind": "任务所属角色：admin管理端或mini小程序端",
            "owner_id": "所属角色或资源的内部标识",
            "payload": "任务执行所需参数的JSON字符串",
            "state": "任务状态：queued待执行、running执行中、retry待重试、succeeded成功、failed失败",  # noqa: E501
            "attempts": "已领取执行的次数",
            "max_attempts": "允许的最大执行次数",
            "available_at": "任务最早可执行时间（UTC，微秒精度）",
            "dispatch_after": "任务下次允许投递队列的时间（UTC，微秒精度）",
            "lease": "当前工作进程持有的租约令牌，防止过期执行覆盖结果",
            "lease_expires_at": "当前任务租约过期时间（UTC，微秒精度）",
            "error_code": "最近处理错误的业务代码；空表示无错误",
            "result": "异步任务的执行结果JSON；尚无结果时为空",
            "created_at": "创建时间（UTC，微秒精度）",
            "updated_at": "最近更新时间（UTC，微秒精度）",
        },
    },
    "learning_access_history": {
        "table": "管理员学习授权或免费配置变更审计快照",
        "columns": {
            "id": "记录内部标识",
            "user_id": "授权变更目标用户标识；全局免费配置变更时可为空",
            "admin_id": "操作管理员标识，关联administrators.id",
            "action": "执行的业务操作名称",
            "before": "变更前授权或免费配置JSON快照",
            "after": "变更后授权或免费配置JSON快照",
            "occurred_at": "操作发生时间（UTC，微秒精度）",
        },
    },
    "learning_authorizations": {
        "table": "用户统一学习授权及有效日期",
        "columns": {
            "user_id": "所属用户内部标识，关联users.id",
            "starts_on": "授权开始的北京时间自然日；空表示尚无授权",
            "expires_on": "授权到期的北京时间自然日，当天结束后失效；空表示无有效授权",
            "revoked_at": "授权撤销时间（UTC）；空表示未撤销",
            "revision": "并发修改校验版本号",
        },
    },
    "learning_free_policy": {
        "table": "场景免费策略历史配置及当前策略版本；当前免费资格以cards.is_free为准",
        "columns": {
            "id": "策略单例标识，固定为1",
            "enabled": "旧版免费策略启用标志；当前资格使用场景独立免费标志",
            "free_count": "旧版按数量选取免费场景的配置；当前已停用，仅保留历史值",
            "revision": "并发修改校验版本号",
        },
    },
    "learning_queue_items": {
        "table": "学习队列内场景的固定顺序",
        "columns": {
            "queue_id": "所属学习队列标识，关联learning_queues.id",
            "position": "项目在所属列表中的顺序位置",
            "card_id": "场景稳定标识，关联cards.id",
        },
    },
    "learning_queues": {
        "table": "用户本轮场景学习队列及来源快照",
        "columns": {
            "id": "记录内部标识",
            "user_id": "所属用户内部标识，关联users.id",
            "source": "队列来源：learning学习、favorites收藏、records记录、day指定日期",
            "day": "来源为day时的北京时间学习日期；其他来源为空",
            "created_at": "创建时间（UTC，微秒精度）",
            "expires_at": "过期时间（UTC，微秒精度）",
        },
    },
    "listening_articles": {
        "table": "听读文章稳定身份、可编辑内容及当前发布版本",
        "columns": {
            "id": "记录内部标识",
            "topic_id": "旧版主题标识；当前直接归属分类，仅保留历史兼容",
            "category_id": "当前所属听读分类标识，关联listening_categories.id",
            "draft_category_id": "待发布草稿的目标分类标识；空表示沿用当前分类",
            "category_order": "当前分类内的文章排序值",
            "draft_category_order": "待发布草稿的分类内排序值；空表示沿用当前排序",
            "is_free": "是否对未获学习授权用户免费开放（0否，1是）",
            "free_revision": "当前免费资格的并发校验版本号",
            "draft_topic_id": "旧版草稿主题标识，保留历史兼容",
            "draft_topic_order": "旧版草稿主题内排序，保留历史兼容",
            "status": "文章状态：draft草稿、published已发布、offline已下架",
            "revision": "并发修改校验版本号",
            "version_id": "当前听读发布版本标识；空表示从未发布",
            "payload": "当前可编辑听读资料JSON，包含中英文正文、词汇和媒体引用",
            "topic_order": "旧版主题内排序值，保留历史兼容",
            "global_order": "历史全局排序值，当前仍用于稳定次序；全局排序编辑入口已停用",
            "batch_id": "生成文章的听读导入批次标识；手动新建时可为空",
            "source_hash": "导入源内容摘要，用于识别相同来源",
            "canonical_hash": "规范化正文、词汇及媒体身份的摘要，用于内容去重",
            "created_at": "创建时间（UTC，微秒精度）",
            "deleted_at": "软删除时间（UTC，微秒精度）；空表示未删除",
        },
    },
    "listening_candidates": {
        "table": "听读导入候选、校验问题及保存去重结果",
        "columns": {
            "id": "记录内部标识",
            "batch_id": "所属听读导入批次标识，关联listening_imports.id",
            "package_id": "所属导入资源包标识",
            "path": "候选资料在资源包内的路径",
            "state": "候选状态，如unreadable不可读、incomplete待补全、duplicate重复、saved已保存",  # noqa: E501
            "payload": "候选听读资料及更新目标绑定JSON",
            "topic_id": "旧版导入目标主题标识，保留历史兼容",
            "category_id": "选定的目标听读分类标识；未选择时为空",
            "source_hash": "导入源内容摘要，用于识别相同来源",
            "canonical_hash": "规范化正文、词汇及媒体身份的摘要，用于内容去重",
            "errors": "源文件解析和内容校验问题JSON列表",
            "resources": "候选资料可用媒体等资源映射JSON",
            "article_id": "成功保存的听读文章标识；尚未保存时为空",
            "duplicate_of": "被判定重复的听读文章或候选标识；非重复时为空",
            "removed": "是否从当前批次移除（0否，1是）",
        },
    },
    "listening_categories": {
        "table": "听读分类及排序",
        "columns": {
            "id": "记录内部标识",
            "name": "中文名称",
            "name_en": "英文名称",
            "sort_order": "排序值，按升序展示",
            "revision": "并发修改校验版本号",
            "deleted_at": "软删除时间（UTC，微秒精度）；空表示未删除",
        },
    },
    "listening_completions": {
        "table": "用户听读文章首次和最近完成事实",
        "columns": {
            "user_id": "所属用户内部标识，关联users.id",
            "article_id": "听读文章稳定标识，关联listening_articles.id",
            "first_completed_at": "首次完成时间（UTC，微秒精度）",
            "last_completed_at": "最近完成时间（UTC，微秒精度）",
            "first_version_id": "首次完成时的不可变发布版本标识",
            "last_version_id": "最近完成时的不可变发布版本标识",
        },
    },
    "listening_daily": {
        "table": "按北京时间自然日记录的听读学习事实",
        "columns": {
            "user_id": "所属用户内部标识，关联users.id",
            "article_id": "听读文章稳定标识，关联listening_articles.id",
            "date": "学习事实所属北京时间自然日",
            "version_id": "关联不可变发布版本标识",
            "accepted_at": "服务端接受操作时间（UTC，微秒精度）",
        },
    },
    "listening_favorites": {
        "table": "用户听读文章收藏关系",
        "columns": {
            "user_id": "所属用户内部标识，关联users.id",
            "article_id": "听读文章稳定标识，关联listening_articles.id",
            "created_at": "创建时间（UTC，微秒精度）",
        },
    },
    "listening_imports": {
        "table": "听读资料导入批次和审阅状态",
        "columns": {
            "id": "记录内部标识",
            "admin_id": "操作管理员标识，关联administrators.id",
            "mode": "听读源资料格式：zip资源包或docx文档",
            "status": "导入批次的审阅或保存阶段状态",
            "revision": "并发修改校验版本号",
            "packages": "导入资源包清单及解析摘要JSON列表",
            "created_at": "创建时间（UTC，微秒精度）",
        },
    },
    "listening_jobs": {
        "table": "独立听读时间轴识别任务及工作租约",
        "columns": {
            "id": "记录内部标识",
            "input_hash": "所处理时间轴的输入摘要，关联listening_timelines.input_hash",
            "state": "识别任务状态：pending待执行、processing处理中、succeeded成功、failed失败、cancelled已取消",  # noqa: E501
            "provider_task_id": "云端语音识别供应商任务标识；尚未提交时为空",
            "attempts": "已领取执行的次数",
            "lease_token": "当前执行租约令牌，用于隔离过期工作进程",
            "lease_until": "当前执行租约截止时间（UTC，微秒精度）",
            "error_code": "最近处理错误的业务代码；空表示无错误",
            "created_at": "创建时间（UTC，微秒精度）",
            "updated_at": "最近更新时间（UTC，微秒精度）",
        },
    },
    "listening_policy": {
        "table": "听读免费策略历史配置及当前策略和目录版本",
        "columns": {
            "id": "策略单例标识，固定为1",
            "free_count": "旧版按数量选取免费文章的配置；当前以文章is_free为准",
            "revision": "并发修改校验版本号",
            "catalog_revision": "听读目录变更版本号，用于并发校验和失效判断",
        },
    },
    "listening_progress": {
        "table": "用户在指定听读发布版本上的阅读和播放进度",
        "columns": {
            "user_id": "所属用户内部标识，关联users.id",
            "article_id": "听读文章稳定标识，关联listening_articles.id",
            "version_id": "关联不可变发布版本标识",
            "reading_position": "原始英文正文Unicode code point字符偏移，非滚动像素",
            "translation_open": "是否展开译文（0否，1是）",
            "audio_position": "音频播放位置（秒）",
            "playback_rate": "音频播放倍速：1、1.25、1.5、1.75、2",
            "updated_at": "最近更新时间（UTC，微秒精度）",
        },
    },
    "listening_timelines": {
        "table": "按正文和音频输入复用的逐词时间轴",
        "columns": {
            "input_hash": "正文及音频输入身份摘要，用于复用时间轴",
            "body_en": "用于时间轴对齐的英文原始正文",
            "audio_id": "用于生成时间轴的原始音频媒体标识",
            "state": (
                "时间轴状态：pending待处理、processing处理中、ready可用、"
                "needs_attention待核对、failed失败、missing输入已移除"
            ),
            "words": "逐词文本及起止时间JSON列表；时间单位毫秒",
            "job_id": "关联独立听读识别任务标识，关联listening_jobs.id",
            "error_code": "最近处理错误的业务代码；空表示无错误",
            "reviewed_at": "管理员确认时间轴时间（UTC）；空表示未确认",
            "reviewed_by": "确认时间轴的管理员标识；未确认时为空",
        },
    },
    "listening_topics": {
        "table": "旧版听读主题层级，保留用于历史兼容；当前文章直接归属分类",
        "columns": {
            "name_en": "英文名称",
            "id": "记录内部标识",
            "category_id": "旧主题所属分类标识，关联listening_categories.id",
            "name": "中文名称",
            "description": "旧主题简介，保留历史兼容",
            "sort_order": "排序值，按升序展示",
            "revision": "并发修改校验版本号",
        },
    },
    "listening_versions": {
        "table": "听读文章不可变已发布版本",
        "columns": {
            "id": "记录内部标识",
            "article_id": "听读文章稳定标识，关联listening_articles.id",
            "payload": "听读不可变发布内容JSON，包含正文、词汇、分类及媒体引用",
            "input_hash": "正文及音频输入身份摘要，用于复用时间轴",
            "published_at": "版本发布时间（UTC，微秒精度）",
        },
    },
    "login_operations": {
        "table": "微信登录幂等操作及加密结果",
        "columns": {
            "key_digest": "幂等键的SHA-256摘要",
            "fingerprint": "规范化请求的SHA-256指纹，用于拒绝同键不同请求",
            "result_cipher": "微信登录结果的Fernet密文，用于幂等重放",
            "expires_at": "过期时间（UTC，微秒精度）",
        },
    },
    "login_throttles": {
        "table": "登录请求限流窗口计数",
        "columns": {
            "key": "登录限流对象的脱敏键",
            "count": "当前限流窗口内的失败计数",
            "window_at": "限流窗口起始时间（UTC，微秒精度）",
        },
    },
    "media": {
        "table": "私有媒体及处理产物元数据",
        "columns": {
            "id": "记录内部标识",
            "owner_kind": "所属业务角色或资源域",
            "owner_id": "所属角色或资源的内部标识",
            "kind": (
                "媒体类型，如image图片、audio原音频、avatar头像、thumbna"
                "il缩略图、audio_playback转码音频、pronunciation发音"
            ),
            "state": "媒体状态：processing处理中、ready可用、failed失败",
            "job_id": "关联异步处理任务标识；空表示尚无任务",
            "storage_key": "私有存储对象键",
            "content_type": "媒体MIME类型",
            "size": "文件大小（字节）",
            "sha256": "文件原始字节的SHA-256摘要",
            "width": "图片宽度（像素）；空表示不适用",
            "height": "图片高度（像素）；空表示不适用",
            "duration": "音频时长（秒）；空表示不适用或尚未解析",
            "thumbnail_id": "缩略图媒体标识；空表示无缩略图",
            "playback_id": "浏览器或小程序可播放的转码音频媒体标识",
            "processing_stage": "媒体解析或转码的当前处理阶段",
            "created_at": "创建时间（UTC，微秒精度）",
        },
    },
    "media_tickets": {
        "table": "绑定用户会话和场景版本的临时媒体访问凭据",
        "columns": {
            "token_digest": "会话或访问令牌的SHA-256摘要，不保存令牌原文",
            "session_digest": "获发访问票据的小程序登录会话摘要",
            "user_id": "所属用户内部标识，关联users.id",
            "card_id": "场景稳定标识，关联cards.id",
            "version_id": "关联不可变发布版本标识",
            "media_id": "关联媒体标识，关联media.id",
            "purpose": "媒体访问用途：content正文或summary列表摘要",
            "expires_at": "过期时间（UTC，微秒精度）",
        },
    },
    "mini_sessions": {
        "table": "小程序用户登录会话",
        "columns": {
            "token_digest": "会话或访问令牌的SHA-256摘要，不保存令牌原文",
            "user_id": "所属用户内部标识，关联users.id",
            "expires_at": "过期时间（UTC，微秒精度）",
        },
    },
    "operations": {
        "table": "业务写操作的持久化幂等结果",
        "columns": {
            "scope": "幂等键所属作用域，与键摘要共同唯一标识操作",
            "key_digest": "幂等键的SHA-256摘要",
            "action": "执行的业务操作名称",
            "fingerprint": "规范化请求的SHA-256指纹，用于拒绝同键不同请求",
            "result": "幂等操作的响应结果JSON快照",
            "accepted_at": "服务端接受操作时间（UTC，微秒精度）",
        },
    },
    "pronunciations": {
        "table": "单词拼写、确认读音和供应商配置对应的合成发音缓存",
        "columns": {
            "cache_key": "拼写、确认读音及供应商配置共同决定的合成缓存摘要",
            "spelling": "词条原始拼写",
            "reading": "确认的合成读音文本",
            "configuration": "语音供应商、音色及合成参数JSON",
            "job_id": "关联异步处理任务标识；空表示尚无任务",
            "media_id": "关联媒体标识，关联media.id",
            "created_at": "创建时间（UTC，微秒精度）",
        },
    },
    "publication_batches": {
        "table": "场景批量发布的审阅批次",
        "columns": {
            "id": "记录内部标识",
            "admin_id": "操作管理员标识，关联administrators.id",
            "created_at": "创建时间（UTC，微秒精度）",
        },
    },
    "publication_items": {
        "table": "批量发布场景的确认快照及逐项任务",
        "columns": {
            "id": "记录内部标识",
            "batch_id": "所属发布批次标识，关联publication_batches.id",
            "card_id": "场景稳定标识，关联cards.id",
            "name": "发布确认时的场景中文名称快照",
            "title_en": "场景英文标题快照",
            "revision": "发布确认绑定的场景草稿版本号",
            "preview_id": "发布确认绑定的预览标识，关联publication_previews.id",
            "job_id": "关联异步处理任务标识；空表示尚无任务",
            "position": "项目在所属列表中的顺序位置",
        },
    },
    "publication_previews": {
        "table": "绑定草稿版本和内容摘要的发布预览凭据",
        "columns": {
            "id": "记录内部标识",
            "card_id": "场景稳定标识，关联cards.id",
            "draft_revision": "预览绑定的草稿版本号，用于阻止过期预览发布",
            "content_hash": "规范化内容的SHA-256摘要，用于校验内容一致性",
            "admin_id": "操作管理员标识，关联administrators.id",
            "expires_at": "过期时间（UTC，微秒精度）",
        },
    },
    "reading_starts": {
        "table": "用户场景阅读开始记录和阅读位置，不计作完成或打卡",
        "columns": {
            "user_id": "所属用户内部标识，关联users.id",
            "card_id": "场景稳定标识，关联cards.id",
            "started_at": "阅读开始时间（UTC，微秒精度）",
            "position": "客户端保存的场景阅读位置JSON；空表示无位置快照",
        },
    },
    "setting_counters": {
        "table": "业务编号及目录、授权等版本计数器",
        "columns": {
            "name": "计数器名称，如user_number、schema_contract或catalog_revision",
            "value": "对应业务序号或版本号的当前值",
        },
    },
    "users": {
        "table": "小程序用户及加密联系方式",
        "columns": {
            "id": "用户内部标识（UUID）",
            "user_number": "用户展示编号的持久正整数序号，用于生成Juya编号",
            "app_id": "所属微信小程序AppID",
            "openid_digest": "微信OpenID的带密钥HMAC-SHA256查找摘要，不保存OpenID原文",
            "nickname": "用户昵称",
            "avatar_id": "头像媒体标识；空表示使用默认头像",
            "phone_cipher": "手机号Fernet密文；空表示未填写",
            "phone_digest": "手机号带密钥HMAC-SHA256查找摘要；空表示未填写",
            "phone_source": "手机号来源：user_entered_unverified表示用户自行填写且未经验证",
            "wechat_cipher": "用户填写的微信号Fernet密文；空表示未填写",
            "wechat_digest": "微信号带密钥HMAC-SHA256查找摘要；空表示未填写",
            "wechat_source": "微信号来源：user_entered_unverified表示用户自行填写且未经验证",
            "profile_version": "昵称和头像资料的并发修改版本号",
            "contact_version": "联系方式的并发修改版本号",
            "registered_at": "注册时间（UTC，微秒精度）",
            "last_login_at": "最近登录时间（UTC，微秒精度）",
            "profile_updated_at": "最近修改昵称或头像时间（UTC）；空表示尚未修改",
            "contact_updated_at": "最近修改联系方式时间（UTC）；空表示尚未修改",
        },
    },
    "alembic_version": {
        "table": "数据库结构迁移版本记录",
        "columns": {"version_num": "当前已完成的Alembic迁移版本号"},
    },
}


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        return
    inspector = sa.inspect(bind)
    tables = {}
    # Complete preflight before MySQL's first implicitly committed DDL.
    actual = set(inspector.get_table_names())
    if actual != set(COMMENTS):
        raise RuntimeError("0025 table inventory differs from the reviewed schema")
    for name, comments in COMMENTS.items():
        table = sa.Table(name, sa.MetaData(), autoload_with=bind)
        if set(table.c.keys()) != set(comments["columns"]):
            raise RuntimeError(f"0025 column inventory differs: {name}")
        tables[name] = table
    original_timeout = bind.scalar(sa.text("SELECT @@SESSION.lock_wait_timeout"))
    bind.execute(sa.text("SET SESSION lock_wait_timeout=5"))
    try:
        for name, table in tables.items():
            comments = COMMENTS[name]
            clauses = []
            for column in table.columns:
                target = comments["columns"][column.name]
                if column.comment == target:
                    continue
                column.comment = target
                definition = str(CreateColumn(column).compile(dialect=bind.dialect))
                clauses.append("MODIFY COLUMN " + definition)
            if table.comment != comments["table"]:
                literal = sa.literal(comments["table"], sa.String()).compile(
                    dialect=bind.dialect, compile_kwargs={"literal_binds": True}
                )
                clauses.append("COMMENT=" + str(literal))
            if clauses:
                quoted = bind.dialect.identifier_preparer.quote(name)
                bind.exec_driver_sql(
                    f"ALTER TABLE {quoted} " + ", ".join(clauses) + ", ALGORITHM=INPLACE, LOCK=NONE"
                )
    finally:
        bind.execute(sa.text(f"SET SESSION lock_wait_timeout={int(original_timeout)}"))


def downgrade():
    raise RuntimeError("Documentation is retained; retry forward instead of downgrading")
