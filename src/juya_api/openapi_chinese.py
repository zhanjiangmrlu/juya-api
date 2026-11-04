"""Chinese documentation metadata, without changing any wire-level contract."""

from typing import Any

from fastapi import FastAPI

from .openapi_field_docs import FIELD_DOCS, FIELD_OVERRIDES, SCHEMA_TITLES
from .openapi_operation_docs import DESCRIPTION_TRANSLATIONS, OPERATION_DOCS, TAG_DOCS

RESPONSE_DESCRIPTIONS = {
    "200": "请求成功",
    "201": "创建成功；若返回异步任务，则仅表示已受理，最终结果请查询任务状态",
    "202": "请求已受理，处理结果请查询任务状态",
    "204": "操作成功，无响应正文",
    "206": "返回所请求的部分资源内容",
    "400": "请求不符合业务规则",
    "401": "尚未登录，或登录凭证已失效",
    "403": "当前身份无权执行该操作",
    "404": "资源不存在，或当前身份不可访问",
    "409": "状态、版本或幂等请求发生冲突，请按错误码处理",
    "410": "资源或功能已不可用",
    "413": "上传内容超出大小限制",
    "415": "不支持该资源格式",
    "416": "请求的资源范围无效",
    "422": "请求参数校验失败，或业务内容不符合要求",
    "429": "请求过于频繁，请稍后重试",
    "500": "服务器暂未完成请求，请按错误信息处理",
    "503": "服务暂不可用，请稍后重试",
}


def _field(schema: dict[str, Any], name: str, component: str = "") -> None:
    docs = FIELD_OVERRIDES.get((component, name), FIELD_DOCS.get(name))
    if docs:
        schema["title"], schema["description"] = docs


def _inline_schema(schema: dict[str, Any], title: str) -> None:
    """Cover inline array/object schemas as well as named component schemas."""
    if "title" in schema:
        schema["title"] = title
    description = schema.get("description")
    if description in DESCRIPTION_TRANSLATIONS:
        schema["description"] = DESCRIPTION_TRANSLATIONS[description]
    for name, field in schema.get("properties", {}).items():
        _field(field, name)
        _inline_schema(field, field.get("title", "字段数据"))
    for key in ("items", "additionalProperties"):
        if isinstance(schema.get(key), dict):
            _inline_schema(schema[key], "数据项")
    for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        for child in schema.get(key, []):
            _inline_schema(child, "数据项")


def localize_schema(schema: dict[str, Any], role: str) -> dict[str, Any]:
    """Annotate an already generated contract in place; identifiers remain intact."""
    label = "管理后台" if role == "admin" else "小程序"
    schema["info"]["title"] = f"句芽英语{label}接口"
    authentication = (
        "管理接口使用管理员 Cookie 会话；写请求按接口要求携带 CSRF 凭证和 Idempotency-Key。"
        if role == "admin"
        else (
            "需登录的接口使用 Authorization: Bearer <业务令牌>；"
            "写请求按接口要求携带 Idempotency-Key。"
        )
    )
    schema["info"]["description"] = (
        f"句芽英语{label}接口文档。{authentication}"
        "字段名、路径、枚举值和错误码为程序调用标识，保留原值。"
        "可空、必填、长度和数值限制以各字段的类型及约束为准。"
    )
    used_tags = set()
    for path, methods in schema.get("paths", {}).items():
        for method, operation in methods.items():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue
            docs = OPERATION_DOCS.get((method, path))
            if docs:
                operation["summary"], operation["description"] = docs
            tags = []
            for tag in operation.get("tags", []):
                translated = TAG_DOCS.get(tag)
                tags.append(translated[0] if translated else tag)
                used_tags.add(tag)
            operation["tags"] = tags
            for parameter in operation.get("parameters", []):
                name = parameter["name"]
                field_docs = FIELD_DOCS.get(name)
                if field_docs:
                    parameter["description"] = field_docs[1]
                    _field(parameter.get("schema", {}), name)
            for status, response in operation.get("responses", {}).items():
                if status in RESPONSE_DESCRIPTIONS:
                    response["description"] = RESPONSE_DESCRIPTIONS[status]
                for media in response.get("content", {}).values():
                    _inline_schema(media.get("schema", {}), operation["summary"] + "响应数据")
            body = operation.get("requestBody")
            if body is not None:
                body["description"] = "请求数据，字段说明和必填约束见下方数据结构。"
                for media in body.get("content", {}).values():
                    _inline_schema(media.get("schema", {}), "请求数据")
    schema["tags"] = [
        {"name": TAG_DOCS[tag][0], "description": TAG_DOCS[tag][1]}
        for tag in sorted(used_tags)
        if tag in TAG_DOCS
    ]
    for name, component in schema.get("components", {}).get("schemas", {}).items():
        title = SCHEMA_TITLES.get(name)
        if title:
            component["title"] = title
        description = component.get("description")
        if description in DESCRIPTION_TRANSLATIONS:
            component["description"] = DESCRIPTION_TRANSLATIONS[description]
        _inline_schema(component, component.get("title", "数据结构"))
        for field_name, field in component.get("properties", {}).items():
            _field(field, field_name, name)
    return schema


def install_chinese_openapi(app: FastAPI, role: str) -> None:
    """Retain FastAPI's route-aware schema cache and localize each new generation."""
    original_openapi = app.openapi
    localized: dict[str, Any] | None = None

    def openapi() -> dict[str, Any]:
        nonlocal localized
        current = original_openapi()
        if current is not localized:
            localized = localize_schema(current, role)
        return localized

    app.openapi = openapi  # type: ignore[method-assign]
