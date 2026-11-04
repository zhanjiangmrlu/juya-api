"""Schema comments remain available to database inspectors and future installations."""

import importlib
from pathlib import Path

from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from juya_api.database import Base


def test_all_model_tables_and_columns_have_chinese_comments():
    for path in Path("src/juya_api").glob("*models.py"):
        importlib.import_module(f"juya_api.{path.stem}")
    missing = []
    for table in Base.metadata.tables.values():
        for name, comment in [
            (table.name, table.comment),
            *[(f"{table.name}.{column.name}", column.comment) for column in table.columns],
        ]:
            if not comment or not any("\u4e00" <= ch <= "\u9fff" for ch in comment):
                missing.append(name)
    assert not missing, f"Missing Chinese schema comments: {missing}"
    ddl = str(CreateTable(Base.metadata.tables["users"]).compile(dialect=mysql.dialect()))
    assert "COMMENT '手机号" in ddl
    assert "COMMENT=" in ddl
