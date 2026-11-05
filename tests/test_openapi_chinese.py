"""Chinese documentation must not alter the callable API contract."""

import re

import pytest
from fastapi.openapi.utils import get_openapi
from fastapi.testclient import TestClient

from juya_api.admin import create_app as admin_app
from juya_api.config import Settings
from juya_api.mini import create_app as mini_app


def chinese(value):
    return isinstance(value, str) and re.search(r"[\u4e00-\u9fff]", value)


@pytest.fixture(params=[admin_app, mini_app], ids=["admin", "mini"])
def documented_app(request):
    settings = Settings(
        environment="test",
        database_url="sqlite:///:memory:",
        field_encryption_key="yK1Xc0sWCxUQxXvHPEgY46iVE1mW6BwJqHWSeg1oEJ4=",
        lookup_key="openapi-localization-isolated-test-only",
    )
    return request.param(settings)


def without_documentation(value, named_properties=False):
    if isinstance(value, list):
        return [without_documentation(v) for v in value]
    if not isinstance(value, dict):
        return value
    return {
        k: without_documentation(v, named_properties=k == "properties")
        for k, v in value.items()
        if named_properties or k not in {"title", "description", "summary", "tags"}
    }


def assert_chinese_metadata(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"title", "description", "summary"} and isinstance(child, str):
                assert chinese(child), (*path, key, child)
            assert_chinese_metadata(child, (*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_chinese_metadata(child, (*path, index))


def test_live_openapi_describes_operations_parameters_and_fields_in_chinese(documented_app):
    schema = TestClient(documented_app).get("/openapi.json").json()
    assert chinese(schema["info"]["title"])
    assert chinese(schema["info"]["description"])
    assert_chinese_metadata(schema)
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            assert chinese(operation["summary"]), (method, path)
            assert chinese(operation["description"]), (method, path)
            assert all(chinese(tag) for tag in operation["tags"]), (method, path)
            for parameter in operation.get("parameters", []):
                assert chinese(parameter["description"]), (path, parameter["name"])
            for response in operation["responses"].values():
                assert chinese(response["description"]), (path, response)
    for name, component in schema["components"]["schemas"].items():
        assert chinese(component["title"]), name
        for field, details in component.get("properties", {}).items():
            assert chinese(details["title"]), (name, field)
            assert chinese(details["description"]), (name, field)


def test_localization_preserves_paths_types_constraints_enums_and_operation_ids(documented_app):
    raw = get_openapi(
        title=documented_app.title,
        version=documented_app.version,
        openapi_version=documented_app.openapi_version,
        description=documented_app.description,
        routes=documented_app.routes,
        separate_input_output_schemas=documented_app.separate_input_output_schemas,
    )
    localized = documented_app.openapi()
    assert without_documentation(localized) == without_documentation(raw)
    assert documented_app.openapi() is localized


def test_documented_units_and_concurrency_fields_are_explicit(documented_app):
    schema = documented_app.openapi()["components"]["schemas"]
    if "TimelineWord" in schema:
        fields = schema["TimelineWord"]["properties"]
        assert "毫秒" in fields["start_ms"]["description"]
        assert "毫秒" in fields["end_ms"]["description"]
    if "DeleteImport" in schema:
        assert "原样" in schema["DeleteImport"]["properties"]["expected_updated_at"]["description"]
