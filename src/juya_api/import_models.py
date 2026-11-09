"""Recoverable import source files, editable review staging and per-card save results."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime
from .models import identifier


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = {"comment": "场景资料导入批次与软删除状态"}
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    admin_id: Mapped[str] = mapped_column(
        ForeignKey("administrators.id"), index=True, comment="操作管理员标识，关联administrators.id"
    )
    mode: Mapped[str] = mapped_column(
        String(16), comment="场景导入模式：zip压缩包、docx文档、single单卡文档"
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, comment="创建时间（UTC，微秒精度）")
    updated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime,
        default=lambda context: context.get_current_parameters()["created_at"],
        comment="导入批次最近活动时间（UTC，微秒精度）；旧记录可为空",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True, comment="软删除时间（UTC，微秒精度）；空表示未删除"
    )


class ImportFile(Base):
    __tablename__ = "import_files"
    __table_args__ = (
        UniqueConstraint("batch_id", "parent_id", "name", "sha256", name="uq_import_file_object"),
        {"comment": "导入源文件、处理任务及进度"},
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("import_batches.id"),
        index=True,
        comment="所属场景导入批次标识，关联import_batches.id",
    )
    parent_id: Mapped[str] = mapped_column(
        String(36), default="", comment="父级导入文件标识；空串表示顶层文件"
    )
    name: Mapped[str] = mapped_column(String(512), comment="导入文件名或包内相对路径")
    kind: Mapped[str] = mapped_column(
        String(16), comment="导入文件类型，用于选择解析或媒体处理流程"
    )
    storage_key: Mapped[str] = mapped_column(String(255), comment="私有存储对象键")
    size: Mapped[int] = mapped_column(Integer, comment="文件大小（字节）")
    sha256: Mapped[str] = mapped_column(String(64), comment="文件原始字节的SHA-256摘要")
    media_id: Mapped[str | None] = mapped_column(
        ForeignKey("media.id"), comment="关联媒体标识，关联media.id"
    )
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id"), comment="关联异步处理任务标识；空表示尚无任务"
    )
    error_code: Mapped[str | None] = mapped_column(
        String(64), comment="最近处理错误的业务代码；空表示无错误"
    )
    progress: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="文件解析阶段及进度JSON快照"
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, comment="创建时间（UTC，微秒精度）")


class ImportItem(Base):
    __tablename__ = "import_items"
    __table_args__ = (
        UniqueConstraint("source_file_id", "source_index", name="uq_import_source_section"),
        {"comment": "场景导入候选内容与逐项保存结果"},
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=identifier, comment="记录内部标识"
    )
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("import_batches.id"),
        index=True,
        comment="所属场景导入批次标识，关联import_batches.id",
    )
    source_file_id: Mapped[str] = mapped_column(
        ForeignKey("import_files.id"), comment="生成候选项的源文件标识，关联import_files.id"
    )
    source_index: Mapped[int] = mapped_column(Integer, comment="候选项在源文件内的位置编号")
    source_identity: Mapped[str] = mapped_column(String(64), comment="候选项的稳定来源身份摘要")
    content: Mapped[dict] = mapped_column(JSON, comment="候选场景草稿内容JSON")
    study_note: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="学习笔记核对决策JSON，保留同包同目录候选、有效及待处理媒体引用",
    )
    parser_issues: Mapped[list] = mapped_column(
        JSON, default=list, comment="解析和内容校验问题JSON列表"
    )
    readable: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="源内容是否可读（0否，1是）"
    )
    selected: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="候选项是否选中保存（0否，1是）"
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, comment="并发修改校验版本号")
    target_card_id: Mapped[str | None] = mapped_column(
        ForeignKey("cards.id"), comment="明确选定的更新目标场景；空表示新建"
    )
    target_revision: Mapped[int | None] = mapped_column(
        Integer, comment="更新目标场景的确认草稿版本号"
    )
    saved_card_id: Mapped[str | None] = mapped_column(
        ForeignKey("cards.id"), comment="最近成功保存的场景标识"
    )
    saved_draft_revision: Mapped[int | None] = mapped_column(
        Integer, comment="最近成功保存后的场景草稿版本号"
    )
    last_saved_hash: Mapped[str | None] = mapped_column(
        String(64), comment="最近成功保存内容的摘要，用于跳过重复保存"
    )
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id"), comment="关联异步处理任务标识；空表示尚无任务"
    )
    position: Mapped[int] = mapped_column(Integer, comment="项目在所属列表中的顺序位置")


class ImportIdentity(Base):
    __tablename__ = "import_identities"
    __table_args__ = {"comment": "场景导入去重身份及最近保存版本"}
    object_key: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="跨批次复用的导入对象身份摘要"
    )
    card_id: Mapped[str] = mapped_column(
        ForeignKey("cards.id"), comment="场景稳定标识，关联cards.id"
    )
    content_hash: Mapped[str] = mapped_column(
        String(64), comment="规范化内容的SHA-256摘要，用于校验内容一致性"
    )
    draft_revision: Mapped[int] = mapped_column(Integer, comment="最近保存到目标场景的草稿版本号")
