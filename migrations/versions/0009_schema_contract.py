"""Initialize the database compatibility contract without changing existing business structures."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.bulk_insert(
        sa.table("setting_counters", sa.column("name", sa.String), sa.column("value", sa.Integer)),
        [{"name": "schema_contract", "value": 1}],
    )


def downgrade():
    op.execute("DELETE FROM setting_counters WHERE name='schema_contract'")
