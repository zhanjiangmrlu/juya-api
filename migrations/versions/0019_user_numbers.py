"""Backfill fixed user numbers in registration order while preserving UUID references.

Stop old registration writers before upgrading: new registrations must supply user_number.
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("user_number", sa.Integer(), nullable=True))
    users = sa.table(
        "users",
        sa.column("id", sa.String(36)),
        sa.column("registered_at", sa.DateTime()),
        sa.column("user_number", sa.Integer()),
    )
    numbered = sa.select(
        users.c.id,
        sa.func.row_number().over(order_by=(users.c.registered_at, users.c.id)).label("number"),
    ).subquery("numbered_users")
    op.execute(
        users.update().values(
            user_number=sa.select(numbered.c.number)
            .where(numbered.c.id == users.c.id)
            .scalar_subquery()
        )
    )
    with op.batch_alter_table("users") as batch:
        batch.alter_column("user_number", existing_type=sa.Integer(), nullable=False)
        batch.create_unique_constraint("uq_user_number", ["user_number"])
        batch.create_check_constraint("ck_user_number_positive", "user_number > 0")
    counters = sa.table(
        "setting_counters", sa.column("name", sa.String(64)), sa.column("value", sa.Integer())
    )
    op.execute(
        counters.insert().from_select(
            ["name", "value"],
            sa.select(
                sa.literal("user_number"), sa.func.coalesce(sa.func.max(users.c.user_number), 0)
            ),
        )
    )


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("ck_user_number_positive", type_="check")
        batch.drop_constraint("uq_user_number", type_="unique")
        batch.drop_column("user_number")
    op.execute("DELETE FROM setting_counters WHERE name='user_number'")
