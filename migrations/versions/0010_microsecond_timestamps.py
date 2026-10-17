"""Preserve accepted instants at microsecond precision; compatible with existing role images."""

from alembic import op
from sqlalchemy import DateTime
from sqlalchemy.dialects.mysql import DATETIME

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

COLUMNS = {
    "cards": {"created_at": False, "deleted_at": True},
    "jobs": {
        "available_at": False,
        "dispatch_after": False,
        "lease_expires_at": True,
        "created_at": False,
        "updated_at": False,
    },
    "login_operations": {"expires_at": False},
    "login_throttles": {"window_at": False},
    "media": {"created_at": False},
    "operations": {"accepted_at": False},
    "users": {
        "registered_at": False,
        "last_login_at": False,
        "profile_updated_at": True,
        "contact_updated_at": True,
    },
    "admin_sessions": {"expires_at": False},
    "audits": {"occurred_at": False},
    "card_drafts": {"updated_at": False},
    "card_versions": {"published_at": False},
    "checkins": {"accepted_at": False},
    "consents": {"accepted_at": False},
    "favorites": {"created_at": False},
    "import_batches": {"created_at": False},
    "mini_sessions": {"expires_at": False},
    "pronunciations": {"created_at": False},
    "publication_batches": {"created_at": False},
    "publication_previews": {"expires_at": False},
    "completions": {"first_completed_at": False, "last_completed_at": False},
    "daily_learning": {"accepted_at": False},
    "import_files": {"created_at": False},
    "media_tickets": {"expires_at": False},
}


def upgrade():
    if op.get_bind().dialect.name != "mysql":
        return
    for table, columns in COLUMNS.items():
        for name, nullable in columns.items():
            op.alter_column(
                table,
                name,
                type_=DATETIME(fsp=6),
                existing_type=DateTime(),
                existing_nullable=nullable,
            )


def downgrade():
    raise RuntimeError("Timestamp precision is retained; roll back only the application image")
