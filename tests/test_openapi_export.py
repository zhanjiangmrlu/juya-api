"""Contract artifacts must remain UTF-8 even on a legacy Windows locale."""

import json
import runpy
from pathlib import Path
from types import SimpleNamespace


def test_export_writes_utf8_independently_of_windows_default_encoding(monkeypatch):
    from juya_api import admin, mini

    schema = {"info": {"title": "句芽管理与听读"}, "paths": {}}

    def factory(**kwargs):
        return SimpleNamespace(openapi=lambda: schema)

    monkeypatch.setattr(admin, "create_app", factory)
    monkeypatch.setattr(mini, "create_app", factory)
    monkeypatch.setattr(Path, "mkdir", lambda *args, **kwargs: None)
    artifacts = {}

    def write_text(target, data, encoding=None, **kwargs):
        # Exercise the Windows GBK default without changing any real artifact or database.
        artifacts[target.name] = data.encode(encoding or "gbk")
        return len(data)

    monkeypatch.setattr(Path, "write_text", write_text)
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts" / "export-openapi.py"))
    assert set(artifacts) == {"admin.json", "mini.json"}
    assert all(json.loads(data.decode("utf-8")) == schema for data in artifacts.values())
