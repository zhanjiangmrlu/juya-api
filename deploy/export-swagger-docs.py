"""Export the same live-contract Swagger view used by local FastAPI."""

import argparse
from pathlib import Path

from juya_api.swagger_docs import render_swagger_html

parser = argparse.ArgumentParser()
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
for role, label in (("admin", "管理后台"), ("mini", "小程序")):
    target = args.output / f"{role}.html"
    target.write_text(render_swagger_html(f"句芽英语{label}接口"), encoding="utf-8")
    print(target)
