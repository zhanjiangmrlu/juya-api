"""Record import changes without inventing activity for existing batches.

Old review-only edits did not persist a timestamp. Their exact time cannot be
reconstructed: retain the latest recorded batch/file/referenced task instant.
The application records review and other batch writes from this revision on.
Keep the added column nullable so a previous image can still insert batches
after expansion or application rollback; new reads fall back to recorded facts.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import DATETIME

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def instant():
    return sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")


def upgrade():
    op.add_column("import_batches", sa.Column("updated_at", instant(), nullable=True))
    batches = sa.table(
        "import_batches",
        sa.column("id", sa.String(36)),
        sa.column("created_at", instant()),
        sa.column("updated_at", instant()),
    )
    files = sa.table(
        "import_files",
        sa.column("batch_id", sa.String(36)),
        sa.column("media_id", sa.String(36)),
        sa.column("job_id", sa.String(36)),
        sa.column("created_at", instant()),
    )
    items = sa.table(
        "import_items", sa.column("batch_id", sa.String(36)), sa.column("job_id", sa.String(36))
    )
    jobs = sa.table(
        "jobs",
        sa.column("id", sa.String(36)),
        sa.column("kind", sa.String(40)),
        sa.column("updated_at", instant()),
    )
    media = sa.table("media", sa.column("id", sa.String(36)), sa.column("job_id", sa.String(36)))
    op.execute(batches.update().values(updated_at=batches.c.created_at))
    sources = [
        sa.select(sa.func.max(files.c.created_at)).where(files.c.batch_id == batches.c.id),
        sa.select(sa.func.max(jobs.c.updated_at))
        .select_from(files.join(jobs, files.c.job_id == jobs.c.id))
        .where(files.c.batch_id == batches.c.id, jobs.c.kind.in_(["import.parse", "media.decode"])),
        sa.select(sa.func.max(jobs.c.updated_at))
        .select_from(items.join(jobs, items.c.job_id == jobs.c.id))
        .where(items.c.batch_id == batches.c.id, jobs.c.kind == "import.save"),
        sa.select(sa.func.max(jobs.c.updated_at))
        .select_from(
            files.join(media, files.c.media_id == media.c.id).join(
                jobs, media.c.job_id == jobs.c.id
            )
        )
        .where(files.c.batch_id == batches.c.id, jobs.c.kind == "media.decode"),
    ]
    for source in sources:
        latest = source.scalar_subquery()
        op.execute(batches.update().where(latest > batches.c.updated_at).values(updated_at=latest))


def downgrade():
    with op.batch_alter_table("import_batches") as batch:
        batch.drop_column("updated_at")
