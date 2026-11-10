"""Add explicit account privacy confirmations and independent optional analysis choices."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade():
    """Expand nullable consent metadata; preserve legacy inserts and all business facts."""
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("consents")}
    for name, kind, comment in (
        ("confirmation_id", sa.String(64), "匿名明确确认记录的关联编号"),
        ("source", sa.String(64), "用户明确确认的入口来源"),
        (
            "client_confirmed_at",
            sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"),
            "客户端确认时间，不代替服务端接受时间",
        ),
    ):
        if name not in columns:
            op.add_column("consents", sa.Column(name, kind, nullable=True, comment=comment))
    if "uq_consent_confirmation" not in {
        u["name"] for u in sa.inspect(bind).get_unique_constraints("consents")
    }:
        with op.batch_alter_table("consents") as batch:
            batch.create_unique_constraint(
                "uq_consent_confirmation", ["user_id", "purpose", "confirmation_id"]
            )
    instant = sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")
    if not sa.inspect(bind).has_table("analytics_preferences"):
        op.create_table(
            "analytics_preferences",
            sa.Column(
                "user_id",
                sa.String(36),
                sa.ForeignKey("users.id"),
                primary_key=True,
                comment="所属稳定账号",
            ),
            sa.Column("enabled", sa.Boolean(), nullable=False, comment="当前账号明确允许统计"),
            sa.Column(
                "scope_version",
                sa.String(64),
                nullable=False,
                comment="实际展示并同意的统计披露版本",
            ),
            sa.Column("revision", sa.Integer(), nullable=False, comment="许可状态并发修订号"),
            sa.Column("enabled_at", instant, nullable=True, comment="本轮明确开启的服务端时间"),
            sa.Column("updated_at", instant, nullable=False, comment="最后一次许可变更时间"),
            comment="独立于登录和学习成绩的账号统计许可",
        )
    if not sa.inspect(bind).has_table("analytics_event_receipts"):
        op.create_table(
            "analytics_event_receipts",
            sa.Column(
                "user_id",
                sa.String(36),
                sa.ForeignKey("users.id"),
                primary_key=True,
                comment="服务端确认的所属账号",
            ),
            sa.Column("event_id", sa.String(64), primary_key=True, comment="事件重试不变的标识"),
            sa.Column("fingerprint", sa.String(64), nullable=False, comment="规范化事件指纹"),
            sa.Column(
                "consent_revision", sa.Integer(), nullable=False, comment="事件发生时的许可修订号"
            ),
            sa.Column("payload", sa.JSON(), nullable=False, comment="仅包含白名单字段的事件"),
            sa.Column("accepted_at", instant, nullable=False, comment="服务端接受时间"),
            comment="通过许可校验的统计事件去重收据，实际传输关闭时不创建",
        )


def downgrade():
    """Retain consent and permission history; rollback deploys compatible older contract-3 code."""
    raise RuntimeError("Privacy consent history must not be destructively removed")
