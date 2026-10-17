"""Export separate contracts without reading credentials or initializing business data."""

import json
from pathlib import Path

from cryptography.fernet import Fernet

from juya_api.admin import create_app as admin_app
from juya_api.config import Settings
from juya_api.mini import create_app as mini_app

root = Path(__file__).resolve().parents[1]
settings = Settings(
    database_url="sqlite:///:memory:",
    field_encryption_key=Fernet.generate_key().decode(),
    lookup_key="contract-export-only-not-used-at-runtime",
)
for name, factory in [("admin", admin_app), ("mini", mini_app)]:
    target = root / "openapi" / f"{name}.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(
        json.dumps(factory(settings=settings).openapi(), ensure_ascii=False, indent=2) + "\n"
    )
    print(target)
