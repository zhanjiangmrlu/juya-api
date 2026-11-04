"""Additive listening domain; scene identities and historic facts remain untouched."""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime, utc_now
from .models import identifier


class ListeningCategory(Base):
    __tablename__ = "listening_categories"
    __table_args__ = {"comment": "听读分类及排序"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    name: Mapped[str] = mapped_column(String(160), comment="中文名称")
    name_en: Mapped[str] = mapped_column(
        String(300), default="", server_default="", comment="英文名称"
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序值，按升序展示")
    revision: Mapped[int] = mapped_column(Integer, default=1, comment="并发修改校验版本号")
    deleted_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, index=True, comment="软删除时间（UTC，微秒精度）；空表示未删除"
    )


class ListeningTopic(Base):
    __tablename__ = "listening_topics"
    __table_args__ = {"comment": "旧版听读主题层级，保留用于历史兼容；当前文章直接归属分类"}
    name_en: Mapped[str] = mapped_column(
        String(300), default="", server_default="", comment="英文名称"
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    category_id: Mapped[str] = mapped_column(
        ForeignKey("listening_categories.id"),
        index=True,
        comment="旧主题所属分类标识，关联listening_categories.id",
    )
    name: Mapped[str] = mapped_column(String(160), comment="中文名称")
    description: Mapped[str] = mapped_column(
        String(2000), default="", server_default="", comment="旧主题简介，保留历史兼容"
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序值，按升序展示")
    revision: Mapped[int] = mapped_column(Integer, default=1, comment="并发修改校验版本号")


class ListeningArticle(Base):
    __tablename__ = "listening_articles"
    __table_args__ = {"comment": "听读文章稳定身份、可编辑内容及当前发布版本"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    topic_id: Mapped[str | None] = mapped_column(
        ForeignKey("listening_topics.id"),
        index=True,
        comment="旧版主题标识；当前直接归属分类，仅保留历史兼容",
    )
    category_id: Mapped[str] = mapped_column(
        ForeignKey("listening_categories.id"),
        index=True,
        comment="当前所属听读分类标识，关联listening_categories.id",
    )
    draft_category_id: Mapped[str | None] = mapped_column(
        ForeignKey("listening_categories.id"),
        comment="待发布草稿的目标分类标识；空表示沿用当前分类",
    )
    category_order: Mapped[int] = mapped_column(
        Integer, default=0, comment="当前分类内的文章排序值"
    )
    draft_category_order: Mapped[int | None] = mapped_column(
        Integer, comment="待发布草稿的分类内排序值；空表示沿用当前排序"
    )
    is_free: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        comment="是否对未获学习授权用户免费开放（0否，1是）",
    )
    free_revision: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", comment="当前免费资格的并发校验版本号"
    )
    draft_topic_id: Mapped[str | None] = mapped_column(
        ForeignKey("listening_topics.id"), comment="旧版草稿主题标识，保留历史兼容"
    )
    draft_topic_order: Mapped[int | None] = mapped_column(
        Integer, comment="旧版草稿主题内排序，保留历史兼容"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default="draft",
        index=True,
        comment="文章状态：draft草稿、published已发布、offline已下架",
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, comment="并发修改校验版本号")
    version_id: Mapped[str | None] = mapped_column(
        String(36), comment="当前听读发布版本标识；空表示从未发布"
    )
    payload: Mapped[dict] = mapped_column(
        JSON, comment="当前可编辑听读资料JSON，包含中英文正文、词汇和媒体引用"
    )
    topic_order: Mapped[int] = mapped_column(
        Integer, default=0, comment="旧版主题内排序值，保留历史兼容"
    )
    global_order: Mapped[int] = mapped_column(
        Integer, default=0, comment="历史全局排序值，当前仍用于稳定次序；全局排序编辑入口已停用"
    )
    batch_id: Mapped[str | None] = mapped_column(
        String(36), index=True, comment="生成文章的听读导入批次标识；手动新建时可为空"
    )
    source_hash: Mapped[str | None] = mapped_column(
        String(64), index=True, comment="导入源内容摘要，用于识别相同来源"
    )
    canonical_hash: Mapped[str | None] = mapped_column(
        String(64), index=True, comment="规范化正文、词汇及媒体身份的摘要，用于内容去重"
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utc_now, comment="创建时间（UTC，微秒精度）"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, index=True, comment="软删除时间（UTC，微秒精度）；空表示未删除"
    )


class ListeningVersion(Base):
    __tablename__ = "listening_versions"
    __table_args__ = {"comment": "听读文章不可变已发布版本"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    article_id: Mapped[str] = mapped_column(
        ForeignKey("listening_articles.id"),
        index=True,
        comment="听读文章稳定标识，关联listening_articles.id",
    )
    payload: Mapped[dict] = mapped_column(
        JSON, comment="听读不可变发布内容JSON，包含正文、词汇、分类及媒体引用"
    )
    input_hash: Mapped[str | None] = mapped_column(
        String(64), comment="正文及音频输入身份摘要，用于复用时间轴"
    )
    published_at: Mapped[datetime] = mapped_column(
        UTCDateTime, comment="版本发布时间（UTC，微秒精度）"
    )


class ListeningPolicy(Base):
    __tablename__ = "listening_policy"
    __table_args__ = {"comment": "听读免费策略历史配置及当前策略和目录版本"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="策略单例标识，固定为1")
    free_count: Mapped[int | None] = mapped_column(
        Integer, comment="旧版按数量选取免费文章的配置；当前以文章is_free为准"
    )
    revision: Mapped[int] = mapped_column(Integer, default=0, comment="并发修改校验版本号")
    catalog_revision: Mapped[int] = mapped_column(
        Integer, default=0, comment="听读目录变更版本号，用于并发校验和失效判断"
    )


class ListeningFavorite(Base):
    __tablename__ = "listening_favorites"
    __table_args__ = {"comment": "用户听读文章收藏关系"}
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), primary_key=True, comment="所属用户内部标识，关联users.id"
    )
    article_id: Mapped[str] = mapped_column(
        ForeignKey("listening_articles.id"),
        primary_key=True,
        comment="听读文章稳定标识，关联listening_articles.id",
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, comment="创建时间（UTC，微秒精度）")


class ListeningCompletion(Base):
    __tablename__ = "listening_completions"
    __table_args__ = {"comment": "用户听读文章首次和最近完成事实"}
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), primary_key=True, comment="所属用户内部标识，关联users.id"
    )
    article_id: Mapped[str] = mapped_column(
        ForeignKey("listening_articles.id"),
        primary_key=True,
        comment="听读文章稳定标识，关联listening_articles.id",
    )
    first_completed_at: Mapped[datetime] = mapped_column(
        UTCDateTime, comment="首次完成时间（UTC，微秒精度）"
    )
    last_completed_at: Mapped[datetime] = mapped_column(
        UTCDateTime, index=True, comment="最近完成时间（UTC，微秒精度）"
    )
    first_version_id: Mapped[str] = mapped_column(
        ForeignKey("listening_versions.id"), comment="首次完成时的不可变发布版本标识"
    )
    last_version_id: Mapped[str] = mapped_column(
        ForeignKey("listening_versions.id"), comment="最近完成时的不可变发布版本标识"
    )


class ListeningDaily(Base):
    __tablename__ = "listening_daily"
    __table_args__ = {"comment": "按北京时间自然日记录的听读学习事实"}
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), primary_key=True, comment="所属用户内部标识，关联users.id"
    )
    article_id: Mapped[str] = mapped_column(
        ForeignKey("listening_articles.id"),
        primary_key=True,
        comment="听读文章稳定标识，关联listening_articles.id",
    )
    date: Mapped[date] = mapped_column(
        Date, primary_key=True, index=True, comment="学习事实所属北京时间自然日"
    )
    version_id: Mapped[str] = mapped_column(
        ForeignKey("listening_versions.id"), comment="关联不可变发布版本标识"
    )
    accepted_at: Mapped[datetime] = mapped_column(
        UTCDateTime, comment="服务端接受操作时间（UTC，微秒精度）"
    )


class ListeningProgress(Base):
    __tablename__ = "listening_progress"
    __table_args__ = {"comment": "用户在指定听读发布版本上的阅读和播放进度"}
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), primary_key=True, comment="所属用户内部标识，关联users.id"
    )
    article_id: Mapped[str] = mapped_column(
        ForeignKey("listening_articles.id"),
        primary_key=True,
        comment="听读文章稳定标识，关联listening_articles.id",
    )
    version_id: Mapped[str] = mapped_column(
        ForeignKey("listening_versions.id"), primary_key=True, comment="关联不可变发布版本标识"
    )
    reading_position: Mapped[int] = mapped_column(
        Integer, comment="原始英文正文Unicode code point字符偏移，非滚动像素"
    )
    translation_open: Mapped[bool] = mapped_column(Boolean, comment="是否展开译文（0否，1是）")
    audio_position: Mapped[float] = mapped_column(Float, comment="音频播放位置（秒）")
    playback_rate: Mapped[float] = mapped_column(
        Float, comment="音频播放倍速：1、1.25、1.5、1.75、2"
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, index=True, comment="最近更新时间（UTC，微秒精度）"
    )


class ListeningTimeline(Base):
    __tablename__ = "listening_timelines"
    __table_args__ = {"comment": "按正文和音频输入复用的逐词时间轴"}
    input_hash: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="正文及音频输入身份摘要，用于复用时间轴"
    )
    body_en: Mapped[str] = mapped_column(Text, comment="用于时间轴对齐的英文原始正文")
    audio_id: Mapped[str] = mapped_column(
        ForeignKey("media.id"), comment="用于生成时间轴的原始音频媒体标识"
    )
    state: Mapped[str] = mapped_column(
        String(24),
        default="pending",
        comment="时间轴状态：pending待处理、processing处理中、ready可用、needs_attention待核对、failed失败、missing输入已移除",
    )
    words: Mapped[list] = mapped_column(
        JSON, default=list, comment="逐词文本及起止时间JSON列表；时间单位毫秒"
    )
    job_id: Mapped[str | None] = mapped_column(
        String(36), comment="关联独立听读识别任务标识，关联listening_jobs.id"
    )
    error_code: Mapped[str | None] = mapped_column(
        String(64), comment="最近处理错误的业务代码；空表示无错误"
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, comment="管理员确认时间轴时间（UTC）；空表示未确认"
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        ForeignKey("administrators.id"), comment="确认时间轴的管理员标识；未确认时为空"
    )


class ListeningJob(Base):
    """Own durable queue/leases, deliberately invisible to the existing scene worker."""

    __tablename__ = "listening_jobs"
    __table_args__ = {"comment": "独立听读时间轴识别任务及工作租约"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    input_hash: Mapped[str] = mapped_column(
        ForeignKey("listening_timelines.input_hash"),
        index=True,
        comment="所处理时间轴的输入摘要，关联listening_timelines.input_hash",
    )
    state: Mapped[str] = mapped_column(
        String(24),
        default="pending",
        index=True,
        comment="识别任务状态：pending待执行、processing处理中、succeeded成功、failed失败、cancelled已取消",
    )
    provider_task_id: Mapped[str | None] = mapped_column(
        String(128), comment="云端语音识别供应商任务标识；尚未提交时为空"
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, comment="已领取执行的次数")
    lease_token: Mapped[str | None] = mapped_column(
        String(36), comment="当前执行租约令牌，用于隔离过期工作进程"
    )
    lease_until: Mapped[datetime | None] = mapped_column(
        UTCDateTime, comment="当前执行租约截止时间（UTC，微秒精度）"
    )
    error_code: Mapped[str | None] = mapped_column(
        String(64), comment="最近处理错误的业务代码；空表示无错误"
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utc_now, comment="创建时间（UTC，微秒精度）"
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utc_now, comment="最近更新时间（UTC，微秒精度）"
    )


class ListeningImport(Base):
    __tablename__ = "listening_imports"
    __table_args__ = {"comment": "听读资料导入批次和审阅状态"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    admin_id: Mapped[str] = mapped_column(
        ForeignKey("administrators.id"), index=True, comment="操作管理员标识，关联administrators.id"
    )
    mode: Mapped[str] = mapped_column(String(16), comment="听读源资料格式：zip资源包或docx文档")
    status: Mapped[str] = mapped_column(
        String(24), default="review", comment="导入批次的审阅或保存阶段状态"
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, comment="并发修改校验版本号")
    packages: Mapped[list] = mapped_column(
        JSON, default=list, comment="导入资源包清单及解析摘要JSON列表"
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utc_now, comment="创建时间（UTC，微秒精度）"
    )


class ListeningCandidate(Base):
    __tablename__ = "listening_candidates"
    __table_args__ = {"comment": "听读导入候选、校验问题及保存去重结果"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("listening_imports.id"),
        index=True,
        comment="所属听读导入批次标识，关联listening_imports.id",
    )
    package_id: Mapped[str] = mapped_column(String(36), comment="所属导入资源包标识")
    path: Mapped[str] = mapped_column(String(512), comment="候选资料在资源包内的路径")
    state: Mapped[str] = mapped_column(
        String(24),
        comment="候选状态，如unreadable不可读、incomplete待补全、duplicate重复、saved已保存",
    )
    payload: Mapped[dict] = mapped_column(JSON, comment="候选听读资料及更新目标绑定JSON")
    topic_id: Mapped[str | None] = mapped_column(
        ForeignKey("listening_topics.id"), comment="旧版导入目标主题标识，保留历史兼容"
    )
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("listening_categories.id"), comment="选定的目标听读分类标识；未选择时为空"
    )
    source_hash: Mapped[str | None] = mapped_column(
        String(64), index=True, comment="导入源内容摘要，用于识别相同来源"
    )
    canonical_hash: Mapped[str | None] = mapped_column(
        String(64), index=True, comment="规范化正文、词汇及媒体身份的摘要，用于内容去重"
    )
    errors: Mapped[list] = mapped_column(
        JSON, default=list, comment="源文件解析和内容校验问题JSON列表"
    )
    resources: Mapped[dict] = mapped_column(
        JSON, default=dict, comment="候选资料可用媒体等资源映射JSON"
    )
    article_id: Mapped[str | None] = mapped_column(
        ForeignKey("listening_articles.id"), comment="成功保存的听读文章标识；尚未保存时为空"
    )
    duplicate_of: Mapped[str | None] = mapped_column(
        String(36), comment="被判定重复的听读文章或候选标识；非重复时为空"
    )
    removed: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否从当前批次移除（0否，1是）"
    )


class ContentMigrationSnapshot(Base):
    """Frozen pre-DDL source for safely resuming MySQL's nontransactional expansion."""

    __tablename__ = "content_migration_snapshots"
    __table_args__ = {"comment": "内容结构迁移前的持久快照，用于中断续迁"}
    id: Mapped[str] = mapped_column(
        String(16), primary_key=True, comment="生成快照的结构迁移版本标识"
    )
    payload: Mapped[dict] = mapped_column(JSON, comment="升级前源数据及确定性映射的冻结JSON快照")
