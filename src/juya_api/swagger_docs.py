"""A compact Swagger view with shared error documentation and a live contract."""

import html
import json

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_oauth2_redirect_html
from fastapi.responses import HTMLResponse

from .openapi_chinese import RESPONSE_DESCRIPTIONS

COMMON_RESPONSES = (
    "\n\n## 公共状态码\n\n"
    "各接口下方仅展示成功响应。错误响应统一按本节处理，具体业务原因见 error.code 和 error.message。"
    "\n\n| HTTP 状态码 | 含义 |\n| --- | --- |\n"
    + "\n".join(
        f"| {code} | {description} |" for code, description in RESPONSE_DESCRIPTIONS.items()
    )
    + "\n\n### 公共错误返回格式\n\n```json\n"
    + json.dumps(
        {
            "error": {
                "code": "operation_conflict",
                "message": "状态已变化，请刷新后重试",
                "details": None,
            },
            "request_id": "请求追踪标识",
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n```\n\n"
    "error.code 为稳定业务错误码，error.message 为可读提示，error.details 为补充信息；"
    "request_id 用于定位请求。实际调用返回的错误响应仍会在调试结果中显示。"
)

VIEW_SCRIPT = (
    "const commonResponses = "
    + json.dumps(COMMON_RESPONSES, ensure_ascii=False)
    + ";\n"
    + r"""
function buildSwaggerDocument(source) {
    const schema = structuredClone(source);
    schema.info.description = (schema.info.description || '') + commonResponses;
    for (const methods of Object.values(schema.paths || {})) {
        for (const operation of Object.values(methods)) {
            if (!operation || typeof operation !== 'object' || !operation.responses) continue;
            operation.responses = Object.fromEntries(
                Object.entries(operation.responses)
                    .filter(([status]) => /^2(?:[0-9]{2}|XX)$/i.test(status))
            );
        }
    }
    return schema;
}
(async function loadDocumentation() {
    try {
        const response = await fetch('/openapi.json', { cache: 'no-store' });
        if (!response.ok) throw new Error('OpenAPI unavailable');
        const canonical = await response.json();
        window.ui = SwaggerUIBundle({
            spec: buildSwaggerDocument(canonical),
            dom_id: '#swagger-ui',
            layout: 'BaseLayout',
            deepLinking: true,
            showExtensions: true,
            showCommonExtensions: true,
            validatorUrl: null,
            oauth2RedirectUrl: window.location.origin + '/docs/oauth2-redirect',
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIBundle.SwaggerUIStandalonePreset
            ]
        });
    } catch (_) {
        document.querySelector('#swagger-ui').textContent = '接口文档加载失败，请刷新重试。';
    }
})();
"""
)


def render_swagger_html(title: str) -> str:
    """Used by local FastAPI and by the test Nginx documentation asset exporter."""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>__TITLE__ - Swagger UI</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    <link rel="icon" href="https://fastapi.tiangolo.com/img/favicon.png">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>__SCRIPT__</script>
</body>
</html>
""".replace("__TITLE__", html.escape(title)).replace("__SCRIPT__", VIEW_SCRIPT)


def install_swagger_docs(app: FastAPI, environment: str) -> None:
    """Register presentation-only routes; keep the canonical OpenAPI untouched."""
    if environment == "production":
        return

    @app.get("/docs", include_in_schema=False, response_class=HTMLResponse)
    async def documentation():
        return HTMLResponse(render_swagger_html(app.title))

    @app.get("/docs/oauth2-redirect", include_in_schema=False, response_class=HTMLResponse)
    async def oauth_redirect():
        return get_swagger_ui_oauth2_redirect_html()
