"""Image compatibility across additive migrations and independently deployed API roles."""

import re

from sqlalchemy import inspect, text

from .content_models import SettingCounter
from .errors import DomainError

MINIMUM_REVISION = 10
CODE_CONTRACT = 1


def require_compatible_schema(db, *, minimum_revision=MINIMUM_REVISION):
    """Allow newer expansion revisions but reject an incomplete schema or retired code contract."""
    inspector = inspect(db.get_bind())
    if not all(
        inspector.has_table(name) for name in ["users", "setting_counters", "alembic_version"]
    ):
        raise DomainError(503, "schema_not_ready", "数据库尚未完成迁移")
    revisions = list(db.scalars(text("SELECT version_num FROM alembic_version")))
    contract = db.get(SettingCounter, "schema_contract")
    if (
        len(revisions) != 1
        or not re.fullmatch(r"\d{4}", revisions[0])
        or int(revisions[0]) < minimum_revision
        or not contract
        or not 1 <= contract.value <= CODE_CONTRACT
    ):
        raise DomainError(503, "schema_incompatible", "数据库与当前服务版本不兼容")
    return revisions[0]
