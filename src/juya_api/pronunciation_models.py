"""One synthesis identity per spelling, confirmed reading and provider configuration."""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime


class Pronunciation(Base):
    __tablename__ = "pronunciations"
    __table_args__ = {"comment": "单词拼写、确认读音和供应商配置对应的合成发音缓存"}
    cache_key: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="拼写、确认读音及供应商配置共同决定的合成缓存摘要"
    )
    spelling: Mapped[str] = mapped_column(String(300), comment="词条原始拼写")
    reading: Mapped[str] = mapped_column(String(300), comment="确认的合成读音文本")
    configuration: Mapped[dict] = mapped_column(JSON, comment="语音供应商、音色及合成参数JSON")
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id"), comment="关联异步处理任务标识；空表示尚无任务"
    )
    media_id: Mapped[str | None] = mapped_column(
        ForeignKey("media.id"), comment="关联媒体标识，关联media.id"
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, comment="创建时间（UTC，微秒精度）")
