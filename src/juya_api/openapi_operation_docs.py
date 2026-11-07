"""管理端与小程序端接口的中文分组、摘要和操作说明。

只包含文档元数据；路径、方法、请求字段和业务处理保持原契约。
"""

TAG_DOCS: dict[str, tuple[str, str]] = {
    "learning authorization": ("学习授权管理", "查询学习授权与变更历史，预览并确认用户授权调整。"),
    "explicit free access": (
        "逐项免费设置",
        "分别管理雅思词汇卡片和听读文章的免费状态及独立版本。",
    ),
    "administrator authentication": ("管理员登录", "管理员身份登录、会话查询与退出。"),
    "scene management": ("雅思词汇管理", "管理原场景卡片的草稿、核对预览与发布状态。"),
    "durable management actions": (
        "词汇卡片批量操作",
        "创建、查询和重试可恢复的卡片批量管理任务。",
    ),
    "private administrator media": ("管理端私有素材", "上传、查询和读取经管理员鉴权的私有素材。"),
    "read-only learners and statistics": (
        "学员与统计查询",
        "只读查询学员资料、学习记录、打卡记录和统计。",
    ),
    "ordering and batch publication": (
        "词汇排序与批量发布",
        "管理词汇卡片顺序及可恢复的批量发布任务。",
    ),
    "recoverable content import": (
        "词汇内容导入",
        "上传和核对内容导入批次，处理候选内容并恢复未完成任务。",
    ),
    "durable write results": ("写入结果查询", "按当前身份和幂等键查询已持久化的成功写入结果。"),
    "controlled word pronunciation": ("词汇发音", "按受控的词汇引用生成发音、查询状态和读取音频。"),
    "private feedback": ("私有反馈", "查询和处理反馈会话、消息、未读状态及受控图片。"),
    "listening administration": ("主题听读管理", "管理听读分类、文章、素材、时间轴及发布状态。"),
    "listening word pronunciation": ("听读词汇发音", "查询和生成听读文章或导入候选词汇的发音。"),
    "listening import staging": ("听读内容导入", "上传听读资料，编辑导入候选并核对保存或发布。"),
    "learning access": ("学习权限", "查询当前用户的学习授权及指定词汇卡片的访问权限。"),
    "learner authentication": ("学习者登录", "通过微信登录，查询当前身份并退出会话。"),
    "published learning content": ("已发布雅思词汇", "分页查询已发布词汇卡片并读取当前有效内容。"),
    "controlled published resources": ("已发布词汇素材", "签发受控素材访问凭证并校验后交付资源。"),
    "personal learning": ("个人词汇学习", "记录词汇学习完成和收藏，查询个人学习状态、记录及打卡。"),
    "personal profile": ("个人资料", "修改本人展示资料和联系方式，上传及读取头像。"),
    "source learning queues": ("来源学习队列", "按来源条件建立本人学习顺序快照，并稳定分页读取。"),
    "trusted reading position": ("阅读位置", "保存同一正文版本中的阅读锚点和相对进度。"),
    "controlled body dictionary": (
        "正文查词与发音",
        "依据正文中的受控词语引用查词、生成发音并读取音频。",
    ),
    "public controlled resources": (
        "游客受控资源",
        "匿名短期票据读取并逐次重验发布免费和当前版本。",
    ),
    "public share summaries": ("公开分享摘要", "读取已发布词汇卡片的公开分享摘要和分享图片。"),
    "thematic listening": (
        "主题听读学习",
        "浏览已发布听读文章，记录进度、完成及收藏，读取受控素材和发音。",
    ),
}

DESCRIPTION_TRANSLATIONS: dict[str, str] = {
    "Reject obsolete configuration writes while retaining role authentication.": (
        "保留管理员身份校验；此旧配置写入接口已停用，返回 410，请使用分类管理和逐项免费设置。"
    ),
    "Read authoritative free state after a pending or unknown response.": (
        "在写入结果待定或未知时，读取当前权威免费状态。"
    ),
    "Change exactly one flag and persist its receipt and audit in the same transaction.": (
        "仅修改指定内容的免费标记，并在同一事务内持久化操作回执和审计记录。"
    ),
    "Recovery is the complete owned set; the default recent-history query stays compatible.": (
        "恢复查询返回本人拥有的完整批次集合；默认查询保持近期历史记录的兼容行为。"
    ),
    "Discard selected ZIP staging atomically; immutable media and receipts remain.": (
        "原子移除选中的 ZIP 暂存内容，保留不可变素材和操作回执。"
    ),
    "Remove only reviewed item revisions, retaining siblings and source archives.": (
        "仅移除已核对版本的指定候选项，保留同批其他候选项及源压缩包。"
    ),
    "Resolve session-bound speech grants and recheck current content before delivery.": (
        "解析与会话绑定的发音访问凭证，并在交付音频前重新校验当前内容。"
    ),
    "List only live categories in configured order.": ("按配置顺序列出未删除的分类。"),
    "Page articles using direct category ownership.": ("按照文章直接所属的分类分页查询。"),
    "Read the complete category order and its shared revision.": (
        "读取分类内完整文章顺序及其共享版本号。"
    ),
    "Read the active publication for administrator history without learner mutations.": (
        "读取当前有效发布内容，供管理员查看发布记录，不写入学习者记录。"
    ),
    "Stream only media referenced by the article's current effective publication.": (
        "仅交付文章当前有效发布版本所引用的素材。"
    ),
    "Read persistent speech state without starting a cloud task.": (
        "读取已持久化的发音状态，不启动云端合成任务。"
    ),
    "Generate one server-resolved vocabulary word with persistent idempotency.": (
        "由服务端解析指定词汇并生成单词发音，使用持久化幂等记录。"
    ),
    "Preview owned staging words without recording any learner facts.": (
        "预览本人导入批次中的候选词汇发音，不记录学习行为。"
    ),
    "Start controlled staging word synthesis against the current batch revision.": (
        "校验当前导入批次版本后，启动候选词汇的受控发音合成。"
    ),
    "Return category progress and an independent continuation target.": (
        "返回各分类的学习进度及独立计算的继续学习目标。"
    ),
    "Page free articles first within their direct category, preserving manual ranks.": (
        "按文章直接所属分类分页，免费文章优先，各组内保留人工顺序。"
    ),
    "Page free publications first, preserving category and article ranks in each group.": (
        "分页列出已发布文章，免费内容优先，各组内保留分类及文章顺序。"
    ),
    "Advance only inside the current category and return its destination ID.": (
        "仅在当前分类内查找下一篇文章，并返回目标文章编号。"
    ),
}

OPERATION_DOCS: dict[tuple[str, str], tuple[str, str]] = {}


def _register(prefix: str, entries: tuple[tuple[str, str, str, str], ...]) -> None:
    """为明确列出的操作登记中文元数据。"""
    for method, path, summary, description in entries:
        OPERATION_DOCS[(method, prefix + path)] = (summary, description)


_register(
    "/api/admin/v1",
    (
        (
            "get",
            "/learning-access/free-policy",
            "查询词汇免费配置",
            "查询当前词汇免费配置及实际免费数量；免费状态以逐项免费设置为准。",
        ),
        (
            "put",
            "/learning-access/free-policy",
            "旧词汇免费配置保存（已停用）",
            DESCRIPTION_TRANSLATIONS[
                "Reject obsolete configuration writes while retaining role authentication."
            ],
        ),
        (
            "get",
            "/learning-access/free-policy/history",
            "查询词汇免费配置历史",
            "分页查询词汇免费配置的审计历史及变更前后值。",
        ),
        (
            "post",
            "/learning-access/free-policy/preview",
            "旧词汇免费配置预览（已停用）",
            DESCRIPTION_TRANSLATIONS[
                "Reject obsolete configuration writes while retaining role authentication."
            ],
        ),
        (
            "get",
            "/users/{user_id}/learning-authorization",
            "查询学员学习授权",
            "查询指定学员当前学习授权、有效期和授权版本。",
        ),
        (
            "put",
            "/users/{user_id}/learning-authorization",
            "确认修改学员学习授权",
            "使用当前管理员的预览凭证确认授权调整；授权版本或业务日期已变化时须重新预览。",
        ),
        (
            "get",
            "/users/{user_id}/learning-authorization/history",
            "查询学员授权历史",
            "分页查询指定学员的授权审计历史及变更前后值。",
        ),
        (
            "post",
            "/users/{user_id}/learning-authorization/preview",
            "预览学员授权调整",
            "预览授予、续期、调整到期日或撤销授权的前后结果，并返回确认凭证。",
        ),
        (
            "get",
            "/cards/{identifier}/free-access",
            "查询词汇卡片免费状态",
            "读取指定词汇卡片的免费标记、独立版本号和实际生效状态，可用于核对未知写入结果。",
        ),
        (
            "put",
            "/cards/{identifier}/free-access",
            "设置词汇卡片免费状态",
            "校验免费设置版本后仅修改指定词汇卡片的免费标记，在同一事务保存操作回执与审计记录。",
        ),
        (
            "get",
            "/listening/articles/{identifier}/free-access",
            "查询听读文章免费状态",
            "读取指定听读文章的免费标记、独立版本号和实际生效状态，可用于核对未知写入结果。",
        ),
        (
            "put",
            "/listening/articles/{identifier}/free-access",
            "设置听读文章免费状态",
            "校验免费设置版本后仅修改指定听读文章的免费标记，在同一事务保存操作回执与审计记录。",
        ),
        (
            "post",
            "/auth/login",
            "管理员登录",
            "校验管理员登录凭据，建立管理端专用会话并返回当前管理员信息。",
        ),
        ("get", "/auth/session", "查询管理员会话", "校验管理端会话并返回当前管理员身份。"),
        ("post", "/auth/logout", "退出管理员登录", "注销当前管理端会话。"),
        (
            "get",
            "/cards",
            "分页查询词汇卡片",
            "按最新发布时间倒序分页，未发布卡片使用创建时间；定位查询使用相同排序。",
        ),
        (
            "post",
            "/cards",
            "创建词汇卡片草稿",
            "使用提交的卡片内容创建候选草稿，并返回卡片详情及草稿版本。",
        ),
        (
            "get",
            "/cards/{card_id}",
            "查询词汇卡片详情",
            "读取指定词汇卡片的管理端详情，包括草稿及当前状态。",
        ),
        (
            "put",
            "/cards/{card_id}",
            "保存词汇卡片草稿",
            "校验草稿版本并保存候选内容，返回更新后的卡片详情。",
        ),
        (
            "delete",
            "/cards/{card_id}",
            "删除词汇卡片",
            "校验卡片版本后执行删除操作，并返回删除结果。",
        ),
        (
            "get",
            "/cards/{card_id}/published",
            "查看词汇卡片已发布版本",
            "只读查询当前有效发布版本的正文，供管理员预览。",
        ),
        (
            "post",
            "/cards/{card_id}/preview",
            "核对词汇卡片发布内容",
            "校验当前草稿版本并生成发布预览，供后续确认发布使用。",
        ),
        (
            "post",
            "/cards/{card_id}/publish",
            "发布词汇卡片",
            "使用已核对的草稿版本和预览编号确认发布。",
        ),
        (
            "post",
            "/cards/{card_id}/offline",
            "下架词汇卡片",
            "校验卡片版本后下架指定卡片，返回更新后的管理端详情。",
        ),
        (
            "get",
            "/card-action-batches",
            "查询近期词汇批量操作",
            "查询当前管理员近期创建的词汇卡片批量操作及逐项处理结果。",
        ),
        (
            "post",
            "/card-action-batches",
            "创建词汇卡片批量操作",
            "为本页选择的最多十张不重复卡片创建批量管理任务，记录可执行项和跳过项。",
        ),
        (
            "get",
            "/card-action-batches/{batch_id}",
            "查询词汇批量操作详情",
            "读取当前管理员的指定批量任务及逐项状态。",
        ),
        (
            "post",
            "/card-action-batches/{batch_id}/retry",
            "重试词汇卡片批量操作",
            "重试本人批量任务中符合重试条件的项目，并返回最新批次状态。",
        ),
        (
            "post",
            "/media",
            "上传管理端私有素材",
            "上传私有素材并返回素材编号和处理状态；允许的类型和大小可从上传配置查询。",
        ),
        (
            "post",
            "/media/{media_id}/retry",
            "重试管理端素材处理",
            "对当前管理员可操作的素材重新执行允许重试的处理流程。",
        ),
        (
            "get",
            "/media/configuration",
            "查询素材上传配置",
            "查询素材上传类型及大小等当前配置限制。",
        ),
        (
            "get",
            "/media/{media_id}",
            "读取管理端私有素材",
            "校验管理员对素材的访问权限后交付可用素材内容。",
        ),
        (
            "get",
            "/media/{media_id}/status",
            "查询管理端素材状态",
            "读取当前管理员可访问素材的元数据与处理状态。",
        ),
        ("get", "/statistics", "查询管理后台统计", "只读查询管理后台概览统计。"),
        ("get", "/users", "分页查询学员", "按查询条件分页读取学员列表，不修改学员成绩或联系方式。"),
        ("get", "/users/{user_id}", "查询学员详情", "只读查询指定学员的管理端详情。"),
        (
            "get",
            "/users/{user_id}/learning-records",
            "查询学员词汇学习记录",
            "分页读取指定学员的词汇学习完成记录。",
        ),
        (
            "get",
            "/users/{user_id}/checkins",
            "查询学员词汇打卡记录",
            "分页读取指定学员的词汇学习打卡记录。",
        ),
        (
            "get",
            "/users/{user_id}/checkins/{day}",
            "查询学员指定日期词汇记录",
            "按业务日期读取指定学员当天的词汇学习记录。",
        ),
        ("get", "/catalog-order", "查询词汇卡片排序", "读取词汇卡片目录顺序及排序版本。"),
        ("put", "/catalog-order", "保存词汇卡片排序", "校验排序版本后保存词汇卡片目录顺序。"),
        (
            "get",
            "/publication-batches",
            "查询近期词汇批量发布",
            "查询当前管理员近期的词汇卡片批量发布任务及结果。",
        ),
        (
            "post",
            "/publication-batches",
            "创建词汇卡片批量发布",
            "按卡片版本和已核对的预览编号创建批量发布任务，同一卡片不可重复选择。",
        ),
        (
            "get",
            "/publication-batches/{batch_id}",
            "查询词汇批量发布详情",
            "读取当前管理员指定批量发布任务的逐项结果。",
        ),
        (
            "post",
            "/publication-batches/{batch_id}/retry",
            "重试词汇卡片批量发布",
            "重试本人批量发布任务中符合重试条件的项目。",
        ),
        ("post", "/imports", "创建词汇导入批次", "为当前管理员创建可恢复的词汇内容导入批次。"),
        (
            "get",
            "/imports",
            "查询词汇导入批次",
            "默认查询近期导入记录；恢复模式返回当前管理员拥有的完整批次集合。",
        ),
        ("get", "/imports/example", "下载词汇导入示例", "下载词汇内容导入示例文件。"),
        (
            "get",
            "/imports/{batch_id}",
            "查询词汇导入批次详情",
            "读取本人指定导入批次的源文件、候选项和处理状态。",
        ),
        (
            "delete",
            "/imports/{batch_id}",
            "删除词汇导入批次",
            "校验本人导入批次状态后删除该批次，返回删除结果。",
        ),
        (
            "post",
            "/imports/{batch_id}/files",
            "上传词汇导入文件",
            "向本人导入批次上传源文件，并返回文件处理状态。",
        ),
        (
            "post",
            "/imports/{batch_id}/files/remove",
            "移除词汇导入源文件",
            "原子移除选中的 ZIP 暂存内容，保留不可变素材和操作回执。",
        ),
        (
            "post",
            "/imports/{batch_id}/items/remove",
            "移除词汇导入候选项",
            "仅移除已核对版本的指定候选项，保留同批其他候选项及源压缩包。",
        ),
        (
            "post",
            "/imports/{batch_id}/files/{file_id}/retry",
            "重试词汇导入文件处理",
            "重试本人批次内指定源文件的处理，返回最新文件状态。",
        ),
        (
            "post",
            "/imports/{batch_id}/resolve",
            "匹配词汇导入候选项",
            "按提交的匹配选择处理本人导入批次中的候选内容。",
        ),
        (
            "patch",
            "/imports/{batch_id}/items/{item_id}",
            "编辑词汇导入候选项",
            "校验候选版本后保存本人导入批次中指定候选项的暂存修改。",
        ),
        (
            "get",
            "/imports/{batch_id}/confirmation",
            "核对词汇导入结果",
            "读取本人导入批次的保存前核对结果。",
        ),
        (
            "post",
            "/imports/{batch_id}/save",
            "保存词汇导入内容",
            "根据提交的核对信息保存本人导入批次的候选内容，并返回批次结果。",
        ),
        (
            "get",
            "/operations/{key}",
            "查询管理端写入结果",
            "按当前管理员身份及幂等键读取已持久化的成功结果；尚无成功回执时返回未找到。",
        ),
        (
            "post",
            "/cards/{card_id}/words/{word_id}/pronunciation",
            "生成词汇卡片单词发音",
            "校验卡片中的指定词汇引用后请求受控发音合成，返回发音状态。",
        ),
        (
            "get",
            "/cards/{card_id}/words/{word_id}/pronunciation",
            "查询词汇卡片单词发音",
            "读取指定词汇的已持久化发音状态与可用音频信息。",
        ),
        (
            "post",
            "/imports/{batch_id}/items/{item_id}/words/{word_id}/pronunciation",
            "生成词汇导入候选单词发音",
            "校验本人导入批次及候选词汇后请求受控发音合成。",
        ),
        (
            "get",
            "/imports/{batch_id}/items/{item_id}/words/{word_id}/pronunciation",
            "查询词汇导入候选单词发音",
            "读取本人导入候选中指定词汇的发音状态。",
        ),
        (
            "get",
            "/pronunciation/{credential}",
            "读取受控词汇发音音频",
            "解析与会话绑定的发音访问凭证，并在交付音频前重新校验当前内容。",
        ),
        ("get", "/feedback", "分页查询学员反馈", "按条件分页查询管理员可访问的反馈会话。"),
        ("get", "/feedback/unread", "查询反馈未读数量", "查询当前管理员的反馈未读统计。"),
        (
            "get",
            "/feedback/images/{image_id}/url",
            "获取反馈图片访问地址",
            "校验反馈图片访问权限后签发受控图片地址。",
        ),
        (
            "get",
            "/feedback/images/{credential}",
            "读取反馈图片",
            "校验图片访问凭证及当前访问权限后交付反馈图片。",
        ),
        (
            "get",
            "/feedback/{feedback_id}",
            "查询反馈会话详情",
            "读取管理员可访问的反馈会话及消息。",
        ),
        (
            "put",
            "/feedback/{feedback_id}/read",
            "标记反馈消息已读",
            "保存当前管理员对指定反馈消息的已读位置。",
        ),
        (
            "post",
            "/feedback/{feedback_id}/messages",
            "回复学员反馈",
            "由当前管理员向指定反馈会话追加回复。",
        ),
    ),
)

_register(
    "/api/admin/v1/listening",
    (
        (
            "put",
            "/categories/order",
            "保存听读分类排序",
            "校验各分类版本后保存完整的听读分类顺序。",
        ),
        (
            "post",
            "/categories/batch-delete",
            "批量删除听读分类",
            "逐项校验分类版本及引用关系，仅删除无下属文章引用的分类，返回逐项结果。",
        ),
        (
            "post",
            "/categories/{identifier}/delete",
            "删除听读分类",
            "校验分类版本及引用关系，仅删除无下属文章引用的分类。",
        ),
        ("get", "/categories", "查询听读分类", "按配置顺序列出未删除的听读分类。"),
        ("post", "/categories", "创建听读分类", "创建听读分类并返回分类详情。"),
        ("put", "/categories/{category_id}", "编辑听读分类", "校验分类版本后保存名称等分类信息。"),
        ("get", "/topics", "查询旧听读主题", "读取兼容接口提供的旧听读主题列表。"),
        (
            "post",
            "/topics",
            "旧听读主题创建（已停用）",
            DESCRIPTION_TRANSLATIONS[
                "Reject obsolete configuration writes while retaining role authentication."
            ],
        ),
        (
            "put",
            "/topics/{topic_id}",
            "旧听读主题编辑（已停用）",
            DESCRIPTION_TRANSLATIONS[
                "Reject obsolete configuration writes while retaining role authentication."
            ],
        ),
        (
            "get",
            "/articles",
            "分页查询听读文章",
            "按文章直接所属分类和筛选条件分页查询管理端文章。",
        ),
        ("post", "/articles", "创建听读文章草稿", "在指定分类下创建听读文章草稿。"),
        (
            "post",
            "/articles/batch-delete",
            "批量删除听读文章",
            "按提交的文章选择和版本执行批量删除，返回逐项结果。",
        ),
        (
            "post",
            "/articles/batch-offline",
            "批量下架听读文章",
            "按提交的文章选择和版本执行批量下架，返回逐项结果。",
        ),
        (
            "post",
            "/articles/batch-publish",
            "批量发布听读文章",
            "校验选中文章的版本和发布条件后逐项发布，返回发布及跳过结果。",
        ),
        (
            "get",
            "/articles/{article_id}",
            "查询听读文章详情",
            "读取指定听读文章的管理端草稿及状态。",
        ),
        (
            "put",
            "/articles/{article_id}",
            "保存听读文章草稿",
            "校验文章版本后保存草稿内容及分类信息。",
        ),
        (
            "post",
            "/articles/{article_id}/preview",
            "核对听读文章发布内容",
            "校验当前文章草稿并生成发布前核对预览。",
        ),
        (
            "post",
            "/articles/{article_id}/publish",
            "发布听读文章",
            "校验文章版本及发布核对信息后发布文章。",
        ),
        (
            "post",
            "/articles/{article_id}/offline",
            "下架听读文章",
            "校验文章版本后下架指定听读文章。",
        ),
        (
            "post",
            "/articles/{article_id}/delete",
            "删除听读文章",
            "校验文章版本后删除指定听读文章。",
        ),
        (
            "get",
            "/order",
            "查询听读文章排序",
            "按查询范围读取完整文章顺序及共享目录版本；旧主题范围映射到对应分类。",
        ),
        (
            "put",
            "/order",
            "保存分类内听读文章排序",
            "仅支持分类内排序；校验共享目录版本后保存该分类完整且无重复的文章顺序。",
        ),
        (
            "get",
            "/free-policy",
            "查询听读免费配置",
            "查询听读免费配置及当前免费文章信息；免费状态以逐项免费设置为准。",
        ),
        (
            "put",
            "/free-policy",
            "旧听读免费配置保存（已停用）",
            DESCRIPTION_TRANSLATIONS[
                "Reject obsolete configuration writes while retaining role authentication."
            ],
        ),
        (
            "post",
            "/free-policy/preview",
            "旧听读免费配置预览（已停用）",
            DESCRIPTION_TRANSLATIONS[
                "Reject obsolete configuration writes while retaining role authentication."
            ],
        ),
        (
            "post",
            "/articles/{article_id}/media",
            "上传听读文章素材",
            "为指定听读文章上传音频或图片等素材，返回素材处理状态。",
        ),
        (
            "get",
            "/articles/{article_id}/media/{media_id}",
            "读取听读文章草稿素材",
            "校验文章与素材的引用关系后交付管理端可访问的素材。",
        ),
        (
            "get",
            "/articles/{article_id}/published",
            "查看听读文章已发布版本",
            "读取当前有效发布内容，供管理员查看发布记录，不写入学习者记录。",
        ),
        (
            "get",
            "/articles/{article_id}/published/media/{media_id}",
            "读取听读文章已发布素材",
            "仅交付文章当前有效发布版本所引用的素材。",
        ),
        (
            "get",
            "/articles/{article_id}/timeline",
            "查询听读文章时间轴",
            "读取文章当前音频时间轴及处理、核对状态。",
        ),
        (
            "put",
            "/articles/{article_id}/timeline",
            "上传听读文章时间轴",
            "校验文章版本后提交手工时间轴数据。",
        ),
        (
            "post",
            "/articles/{article_id}/timeline/retry",
            "重试听读时间轴处理",
            "校验文章版本后重试当前音频的时间轴处理。",
        ),
        (
            "post",
            "/articles/{article_id}/timeline/review",
            "确认听读文章时间轴",
            "校验文章版本后确认已核对的时间轴。",
        ),
        (
            "get",
            "/users/{user_id}/records",
            "查询学员听读记录",
            "分页只读查询指定学员的听读文章学习记录。",
        ),
        (
            "get",
            "/users/{user_id}/checkins/{day}",
            "查询学员指定日期综合学习记录",
            "按业务日期只读查询指定学员当天的词汇和听读学习记录。",
        ),
        (
            "get",
            "/articles/{article_id}/words/{word_id}/pronunciation",
            "查询听读文章词汇发音",
            "读取已持久化的发音状态，不启动云端合成任务。",
        ),
        (
            "post",
            "/articles/{article_id}/words/{word_id}/pronunciation",
            "生成听读文章词汇发音",
            "由服务端解析指定词汇并生成单词发音，使用持久化幂等记录。",
        ),
        (
            "get",
            "/imports/{batch_id}/candidates/{candidate_id}/words/{word_id}/pronunciation",
            "查询听读导入候选词汇发音",
            "预览本人导入批次中的候选词汇发音，不记录学习行为。",
        ),
        (
            "post",
            "/imports/{batch_id}/candidates/{candidate_id}/words/{word_id}/pronunciation",
            "生成听读导入候选词汇发音",
            "校验当前导入批次版本后，启动候选词汇的受控发音合成。",
        ),
        ("get", "/template", "下载听读导入模板", "下载听读内容导入使用的 DOCX 模板。"),
        (
            "post",
            "/docx-preview",
            "解析预览听读文档",
            "解析上传的 DOCX 文档并返回正文、提示及匹配分类，供导入前核对。",
        ),
        (
            "get",
            "/imports/{batch_id}/media/{media_id}",
            "读取听读导入暂存素材",
            "校验本人导入批次与候选素材引用关系后交付可用素材。",
        ),
        (
            "get",
            "/imports/{batch_id}/candidates/{candidate_id}/timeline",
            "查询听读导入候选时间轴",
            "读取本人导入候选当前音频的时间轴及核对状态。",
        ),
        (
            "put",
            "/imports/{batch_id}/candidates/{candidate_id}/timeline",
            "上传听读导入候选时间轴",
            "校验本人批次版本及候选素材后提交手工时间轴。",
        ),
        (
            "post",
            "/imports/{batch_id}/candidates/{candidate_id}/timeline/{action}",
            "重试或确认听读导入候选时间轴",
            "校验本人批次版本后，按 action 执行时间轴重试或核对确认。",
        ),
        ("post", "/imports", "创建听读导入批次", "为当前管理员创建听读资料暂存批次。"),
        ("get", "/imports", "分页查询听读导入批次", "分页读取当前管理员的听读导入批次及处理状态。"),
        (
            "get",
            "/imports/{batch_id}",
            "查询听读导入批次详情",
            "读取本人批次，重新核对重复候选及旧来源确认问题，不改写候选正文。",
        ),
        (
            "post",
            "/imports/{batch_id}/files",
            "上传听读导入文件",
            "向本人导入批次上传文档和配套素材，返回候选及文件处理结果。",
        ),
        (
            "put",
            "/imports/{batch_id}/candidates/{candidate_id}",
            "编辑听读导入候选",
            "校验本人批次版本后保存指定候选的正文、分类及目标文章绑定。",
        ),
        (
            "post",
            "/imports/{batch_id}/remove",
            "移除听读导入候选",
            "校验本人批次版本后移除选中的候选内容。",
        ),
        (
            "post",
            "/imports/{batch_id}/preview",
            "核对听读导入保存或发布",
            "预览所选候选的新建或更新内容，返回绑定批次版本、候选指纹和提交方式的确认凭证。",
        ),
        (
            "post",
            "/imports/{batch_id}/save",
            "确认保存或发布听读导入",
            "使用预览凭证核对批次、候选指纹及提交方式，逐项保存草稿或发布并返回结果。",
        ),
    ),
)

_register(
    "/api/mini/v1",
    (
        (
            "get",
            "/learning-access",
            "查询本人学习权限",
            "查询当前学习者的统一学习授权及免费内容配置。",
        ),
        (
            "get",
            "/cards/{card_id}/access",
            "查询词汇卡片学习权限",
            "查询指定词汇卡片的个人摘要和当前学习访问权限。",
        ),
        (
            "post",
            "/auth/wechat",
            "微信登录",
            "使用微信登录凭据建立小程序专用会话，返回当前学习者身份。",
        ),
        ("get", "/me", "查询本人资料", "校验小程序会话并返回当前学习者资料。"),
        ("post", "/auth/logout", "退出小程序登录", "注销当前小程序学习者会话。"),
        (
            "get",
            "/cards",
            "分页查询已发布词汇卡片",
            "先按本人完成记录过滤，免费内容优先，各组内保留人工顺序，再进行分页。",
        ),
        (
            "get",
            "/cards/{card_id}",
            "读取词汇卡片学习内容",
            "读取卡片当前版本，沿用mark_started记录正文首次有效打开，不计完成。require_study_note=true要求当前有效发布PDF；失效409且不新增开始记录。",
        ),
        (
            "get",
            "/cards/{card_id}/media/{media_id}/url",
            "获取词汇素材访问地址",
            "校验本人对卡片发布版本及素材的访问权限后签发受控访问地址。",
        ),
        (
            "get",
            "/media/{credential}",
            "读取受控词汇素材",
            "校验素材访问凭证和当前内容权限后交付素材。",
        ),
        ("get", "/me/statistics", "查询本人学习统计", "读取当前学习者的个人学习统计。"),
        (
            "post",
            "/cards/{card_id}/complete",
            "完成词汇卡片学习",
            "校验当前用户权限及发布版本后记录学习完成，并返回完成与打卡结果。",
        ),
        (
            "put",
            "/cards/{card_id}/favorite",
            "收藏词汇卡片",
            "校验当前用户权限和发布版本后收藏指定词汇卡片。",
        ),
        (
            "delete",
            "/favorites/{card_id}",
            "取消词汇卡片收藏",
            "移除当前用户对指定词汇卡片的收藏。",
        ),
        (
            "get",
            "/favorites",
            "分页查询本人词汇收藏",
            "分页读取当前用户收藏的词汇卡片摘要及可用状态。",
        ),
        (
            "get",
            "/cards/{card_id}/state",
            "查询词汇卡片个人状态",
            "读取当前用户对指定已发布卡片的学习、收藏和访问状态。",
        ),
        (
            "get",
            "/cards/{card_id}/summary",
            "查询个人记录中的词汇摘要",
            "读取本人收藏或完成记录中指定词汇卡片的摘要及当前状态。",
        ),
        (
            "get",
            "/me/learning-records",
            "分页查询本人词汇学习记录",
            "分页读取当前用户的词汇学习完成记录。",
        ),
        ("get", "/me/checkins", "分页查询本人词汇打卡", "分页读取当前用户的词汇学习打卡记录。"),
        (
            "get",
            "/me/checkins/{day}",
            "查询本人指定日期词汇记录",
            "按业务日期读取本人当天的词汇学习记录。",
        ),
        (
            "get",
            "/configuration",
            "查询小程序配置",
            "查询当前小程序配置，包括以字节为单位的头像上传大小限制。",
        ),
        (
            "patch",
            "/me/profile",
            "修改本人展示资料",
            "校验展示资料版本后更新昵称或头像；头像须为本人已处理完成的上传素材。",
        ),
        (
            "patch",
            "/me/contact",
            "修改本人联系方式",
            "校验联系方式版本后更新本人提交的手机号或微信联系方式，并记录对应同意版本。",
        ),
        ("post", "/me/avatar", "上传本人头像", "上传当前用户头像并返回素材编号及处理状态。"),
        (
            "get",
            "/me/avatar/{media_id}/status",
            "查询本人头像处理状态",
            "读取当前用户指定头像素材的处理状态。",
        ),
        (
            "post",
            "/me/avatar/{media_id}/retry",
            "重试本人头像处理",
            "重试当前用户头像素材允许重新执行的处理流程。",
        ),
        ("get", "/me/avatar-url", "获取本人头像访问地址", "为当前用户头像签发受控访问地址。"),
        ("get", "/avatar/{credential}", "读取受控头像", "校验头像访问凭证及其绑定会话后交付头像。"),
        (
            "get",
            "/operations/{key}",
            "查询小程序写入结果",
            "按当前学习者身份及幂等键读取已持久化的成功结果；尚无成功回执时返回未找到。",
        ),
        (
            "post",
            "/cards/{card_id}/words/{word_id}/pronunciation",
            "生成词汇卡片单词发音",
            "校验本人权限及服务端词汇引用后请求受控单词发音合成。",
        ),
        (
            "get",
            "/cards/{card_id}/words/{word_id}/pronunciation",
            "查询词汇卡片单词发音",
            "读取当前可访问卡片中指定词汇的发音状态及音频信息。",
        ),
        (
            "get",
            "/pronunciation/{credential}",
            "读取受控词汇发音音频",
            "解析与会话绑定的发音访问凭证，并在交付音频前重新校验当前内容。",
        ),
        (
            "post",
            "/learning-queues",
            "创建来源学习队列",
            "为当前用户的来源条件建立可幂等恢复的固定顺序快照。",
        ),
        (
            "get",
            "/learning-queues/{queue_id}",
            "读取本人来源学习队列",
            "读取本人快照索引，失效项保留原位置，避免分页位置变化。",
        ),
        (
            "put",
            "/cards/{card_id}/reading-position",
            "保存词汇卡片阅读位置",
            "保存当前用户在卡片同版正文中的锚点和块内相对进度。",
        ),
        (
            "get",
            "/cards/{card_id}/dictionary",
            "查询词汇卡片正文词义",
            "根据正文中的受控词语引用查询词义，校验当前正文及学习权限。",
        ),
        (
            "post",
            "/cards/{card_id}/dictionary/pronunciation",
            "生成词汇卡片正文词语发音",
            "按正文受控词语引用请求发音合成，返回发音状态。",
        ),
        (
            "get",
            "/cards/{card_id}/dictionary/pronunciation",
            "查询词汇卡片正文词语发音",
            "读取正文指定词语引用的已持久化发音状态。",
        ),
        (
            "get",
            "/dictionary-pronunciation/{credential}",
            "读取正文查词发音音频",
            "校验正文查词发音凭证及当前内容权限后交付音频。",
        ),
        ("get", "/feedback", "分页查询本人反馈", "分页读取当前用户自己的反馈会话。"),
        ("post", "/feedback", "提交反馈", "为当前用户创建反馈会话，可关联本人已上传的反馈图片。"),
        ("get", "/feedback/unread", "查询本人反馈未读数量", "读取当前用户反馈会话的未读统计。"),
        (
            "post",
            "/feedback/images",
            "上传反馈图片",
            "为当前用户上传私有反馈图片，供反馈会话引用。",
        ),
        (
            "get",
            "/feedback/images/{image_id}/url",
            "获取反馈图片访问地址",
            "校验本人反馈图片访问权限后签发受控图片地址。",
        ),
        (
            "get",
            "/feedback/images/{credential}",
            "读取反馈图片",
            "校验图片访问凭证及本人当前访问权限后交付反馈图片。",
        ),
        (
            "get",
            "/feedback/{feedback_id}",
            "查询本人反馈详情",
            "读取属于当前用户的反馈会话和消息。",
        ),
        (
            "put",
            "/feedback/{feedback_id}/read",
            "标记本人反馈消息已读",
            "保存当前用户在本人反馈会话中的已读位置。",
        ),
        (
            "post",
            "/feedback/{feedback_id}/messages",
            "追加反馈消息",
            "向本人反馈会话追加消息及允许引用的图片。",
        ),
        (
            "get",
            "/public/cards/{card_id}/share",
            "查询词汇卡片公开分享摘要",
            "读取已发布词汇卡片可公开展示的分享摘要。",
        ),
        (
            "get",
            "/public/cards/{card_id}/share/images/{version_id}/{variant}",
            "读取词汇卡片分享图片",
            "按卡片发布版本及图片样式读取公开分享图片。",
        ),
    ),
)

_register(
    "/api/mini/v1/listening",
    (
        (
            "get",
            "/home",
            "查询主题听读首页",
            "返回各分类学习进度、独立计算的继续学习目标及本人授权和学习统计。",
        ),
        (
            "get",
            "/topics",
            "查询兼容听读主题列表",
            "读取兼容接口提供的听读主题及学习进度，可按分类筛选。",
        ),
        (
            "get",
            "/topics/{topic_id}/articles",
            "查询旧主题所属分类文章",
            "按旧主题对应的直接分类分页查询文章，免费文章优先，各组内保留人工顺序。",
        ),
        (
            "get",
            "/articles",
            "分页查询已发布听读文章",
            "可按分类筛选；免费内容优先，各组内保留分类及文章顺序。",
        ),
        ("get", "/favorites", "分页查询本人听读收藏", "分页读取本人收藏的听读文章摘要及可用状态。"),
        ("get", "/records", "分页查询本人听读记录", "分页读取本人的听读文章学习记录。"),
        (
            "get",
            "/statistics",
            "查询本人综合学习统计",
            "读取当前学习者的词汇、听读和统一打卡统计。",
        ),
        (
            "get",
            "/checkins",
            "分页查询本人综合打卡",
            "分页读取本人统一打卡记录，包含每天完成的词汇卡片数量和听读文章数量。",
        ),
        (
            "get",
            "/checkins/{day}",
            "查询本人指定日期综合学习记录",
            "按业务日期读取本人当天的词汇和听读学习记录。",
        ),
        (
            "get",
            "/articles/{article_id}/summary",
            "查询听读文章个人摘要",
            "读取指定听读文章的摘要及本人学习、收藏和可用状态。",
        ),
        (
            "get",
            "/articles/{article_id}",
            "读取听读文章学习内容",
            "校验本人学习权限后读取文章当前有效发布内容及个人进度。",
        ),
        (
            "get",
            "/articles/{article_id}/next",
            "查询同分类下一篇听读文章",
            "仅在当前分类内查找下一篇文章，并返回目标文章编号。",
        ),
        (
            "put",
            "/articles/{article_id}/progress",
            "保存听读文章学习进度",
            "校验本人权限和发布版本后保存音频播放及正文阅读进度。",
        ),
        (
            "post",
            "/articles/{article_id}/complete",
            "完成听读文章学习",
            "校验本人权限和文章发布版本后记录学习完成，并返回完成结果。",
        ),
        (
            "put",
            "/articles/{article_id}/favorite",
            "收藏听读文章",
            "校验本人权限和文章发布版本后添加收藏。",
        ),
        (
            "delete",
            "/favorites/{article_id}",
            "取消听读文章收藏",
            "移除当前用户对指定听读文章的收藏。",
        ),
        (
            "get",
            "/articles/{article_id}/media/{media_id}",
            "读取听读文章受控素材",
            "校验本人对指定文章发布版本的学习权限及素材引用后交付素材。",
        ),
        (
            "get",
            "/articles/{article_id}/thumbnail",
            "读取听读文章缩略图",
            "校验文章发布版本和缩略图引用后交付列表缩略图。",
        ),
        (
            "get",
            "/articles/{article_id}/thumbnail-ticket",
            "获取听读缩略图访问凭证",
            "为指定文章发布版本的缩略图签发短期访问凭证。",
        ),
        (
            "post",
            "/articles/{article_id}/media-ticket",
            "获取听读素材访问凭证",
            "校验本人学习权限及素材引用后签发短期访问凭证；凭证刷新不创建持久化写入结果。",
        ),
        (
            "get",
            "/media/{credential}",
            "凭证读取听读素材或发音",
            "校验短期凭证及其对应资源的当前访问条件后，交付文章素材、缩略图或词语发音。",
        ),
        (
            "get",
            "/articles/{article_id}/dictionary",
            "查询听读正文词义",
            "根据听读正文受控词语引用查询词义，并校验本人学习权限。",
        ),
        (
            "post",
            "/articles/{article_id}/dictionary/pronunciation",
            "生成听读正文词语发音",
            "根据听读正文受控词语引用请求发音合成，返回发音状态。",
        ),
        (
            "get",
            "/articles/{article_id}/dictionary/pronunciation",
            "查询听读正文词语发音",
            "读取指定听读正文词语的已持久化发音状态。",
        ),
        (
            "get",
            "/articles/{article_id}/words/{word_id}/pronunciation",
            "查询听读文章词汇发音",
            "读取已持久化的发音状态，不启动云端合成任务。",
        ),
        (
            "post",
            "/articles/{article_id}/words/{word_id}/pronunciation",
            "生成听读文章词汇发音",
            "由服务端解析指定词汇并生成单词发音，使用持久化幂等记录。",
        ),
    ),
)


# 整合08公共读取补充；保留既有操作标识及请求路径。
OPERATION_DOCS[("get", "/api/mini/v1/public/resources/{credential}")] = (
    "读取游客受控资源",
    "校验独立公开票据的用途、有效期、当前发布及免费权限和版本，支持GET、HEAD与Range；不依赖本人会话，不返回永久存储地址。",
)
for _path in (
    "/api/mini/v1/cards",
    "/api/mini/v1/cards/{card_id}",
    "/api/mini/v1/cards/{card_id}/summary",
    "/api/mini/v1/cards/{card_id}/media/{media_id}/url",
    "/api/mini/v1/listening/home",
    "/api/mini/v1/listening/topics",
    "/api/mini/v1/listening/articles",
    "/api/mini/v1/listening/topics/{topic_id}/articles",
    "/api/mini/v1/listening/articles/{article_id}",
    "/api/mini/v1/listening/articles/{article_id}/summary",
    "/api/mini/v1/listening/articles/{article_id}/thumbnail",
    "/api/mini/v1/listening/articles/{article_id}/thumbnail-ticket",
):
    _method = "get"
    _summary, _description = OPERATION_DOCS[(_method, _path)]
    OPERATION_DOCS[(_method, _path)] = (
        _summary,
        _description
        + (
            " 无Authorization时允许游客读取当前发布列表、安全摘要及免费正文/资源，"
            "个人字段为null；非空无效凭据返回401。"
        ),
    )
OPERATION_DOCS[("get", "/api/mini/v1/cards/{card_id}/summary")] = (
    "读取当前发布或本人历史词汇摘要",
    "游客可读当前发布安全摘要；下线及删除摘要继续要求本人收藏或完成归属。摘要不含正文、词汇原句或PDF元信息。",
)
OPERATION_DOCS[("get", "/api/mini/v1/cards")] = (
    "分页查询已发布词汇卡片",
    "游客按全部发布集合查询，显式uncompleted也按published处理且个人字段为null；已登录先按本人完成记录过滤。免费优先、人工顺序及有效PDF过滤在分页前执行。",
)
for _prefix, _object in (("", "cards/{card_id}"), ("/listening", "articles/{article_id}")):
    for _method in ("get", "post"):
        _path = f"/api/mini/v1{_prefix}/{_object}/words/{{word_id}}/pronunciation"
        _summary, _description = OPERATION_DOCS[(_method, _path)]
        OPERATION_DOCS[(_method, _path)] = (
            _summary,
            _description
            + (
                " 游客仅允许当前发布免费预置词汇及版本引用，复用共享缓存和任务，"
                "不创建用户或个人幂等记录；不允许任意文本及正文点词。"
            ),
        )
