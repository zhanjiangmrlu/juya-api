"""Execute the served Swagger page to verify its response presentation."""

import json
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from juya_api.admin import create_app as admin_app
from juya_api.config import Settings
from juya_api.mini import create_app as mini_app


def settings(environment="test"):
    value = Settings(
        environment="test",
        database_url="sqlite:///:memory:",
        field_encryption_key="yK1Xc0sWCxUQxXvHPEgY46iVE1mW6BwJqHWSeg1oEJ4=",
        lookup_key="swagger-presentation-isolated-test-only",
    )
    return value.model_copy(update={"environment": environment})


def execute_page(html, schema):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required to execute the Swagger presentation script")
    scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, re.S)
    script = "\n".join(scripts)
    harness = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
let displayed;
const bundle = options => { displayed = options.spec; return {}; };
bundle.presets = { apis: {}, SwaggerUIStandalonePreset: {} };
const element = { textContent: '' };
const context = vm.createContext({
  structuredClone,
  SwaggerUIBundle: bundle,
  window: { location: { origin: 'https://testserver' } },
  document: { querySelector: () => element },
  fetch: async () => ({ ok: true, json: async () => input.schema }),
});
vm.runInContext(input.script, context);
setImmediate(() => process.stdout.write(JSON.stringify({
  displayed, original: input.schema, error: element.textContent,
})));
"""
    result = subprocess.run(
        [node, "-e", harness],
        input=json.dumps({"script": script, "schema": schema}),
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("factory", [admin_app, mini_app], ids=["admin", "mini"])
def test_swagger_shows_shared_errors_once_and_only_success_per_operation(factory):
    client = TestClient(factory(settings()))
    canonical = client.get("/openapi.json").json()
    page = client.get("/docs")
    assert page.status_code == 200
    result = execute_page(page.text, canonical)
    assert not result["error"]
    assert result["original"] == canonical
    displayed = result["displayed"]
    assert displayed["info"]["description"].count("## 公共状态码") == 1
    assert "公共错误返回格式" in displayed["info"]["description"]
    assert '"request_id"' in displayed["info"]["description"]
    assert displayed["components"] == canonical["components"]
    for path, methods in canonical["paths"].items():
        for method, original in methods.items():
            if "responses" not in original:
                continue
            responses = displayed["paths"][path][method]["responses"]
            assert responses == {
                status: response
                for status, response in original["responses"].items()
                if status.startswith("2")
            }
            assert responses, (method, path)
            assert "401" in original["responses"]
    assert client.get("/openapi.json").json() == canonical


@pytest.mark.parametrize("factory", [admin_app, mini_app], ids=["admin", "mini"])
def test_custom_docs_preserve_oauth_callback_and_production_docs_closed(factory):
    client = TestClient(factory(settings()))
    assert client.get("/docs/oauth2-redirect").status_code == 200
    production = TestClient(factory(settings("production")))
    assert production.get("/docs").status_code == 404


def test_display_retains_partial_content_and_suppresses_default_errors():
    from juya_api.swagger_docs import render_swagger_html

    schema = {
        "openapi": "3.1.0",
        "info": {"title": "测试", "version": "1"},
        "paths": {
            "/audio": {
                "get": {
                    "responses": {
                        "200": {"description": "完整音频"},
                        "206": {"description": "部分音频", "headers": {"Content-Range": {}}},
                        "404": {"description": "资源不存在"},
                        "default": {"description": "其他错误"},
                    }
                }
            }
        },
    }
    result = execute_page(render_swagger_html("测试"), schema)
    assert result["displayed"]["paths"]["/audio"]["get"]["responses"] == {
        "200": {"description": "完整音频"},
        "206": {"description": "部分音频", "headers": {"Content-Range": {}}},
    }
    assert result["original"] == schema
