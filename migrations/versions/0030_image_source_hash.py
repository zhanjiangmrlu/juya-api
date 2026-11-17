"""Keep source identity when new content images are compressed before storage."""

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade():
    """Add nullable source digest without rewriting any historical media."""
    bind = op.get_bind()
    if "source_sha256" not in {c["name"] for c in sa.inspect(bind).get_columns("media")}:
        op.add_column(
            "media",
            sa.Column(
                "source_sha256",
                sa.String(64),
                nullable=True,
                comment="图片转换前原始文件SHA-256；空值使用sha256",
            ),
        )
    if "ix_media_source_sha256" not in {i["name"] for i in sa.inspect(bind).get_indexes("media")}:
        op.create_index("ix_media_source_sha256", "media", ["source_sha256"])


def downgrade():
    """Source identity must not be discarded on a running installation."""
    raise RuntimeError("Expansion migrations are not automatically reversible")
