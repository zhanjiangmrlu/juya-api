from .content_helpers import draft, key, publish


def test_list_and_detail_include_actual_completion_and_favorite_state(admin, mini):
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    assert (
        mini.post(
            f"/api/mini/v1/cards/{card['id']}/complete", headers=key(), json={"version_id": version}
        ).status_code
        == 200
    )
    assert (
        mini.put(
            f"/api/mini/v1/cards/{card['id']}/favorite", headers=key(), json={"version_id": version}
        ).status_code
        == 200
    )
    listing = mini.get("/api/mini/v1/cards").json()
    assert listing["items"] == []
    assert listing["published_total"] == 1
    detail = mini.get(f"/api/mini/v1/cards/{card['id']}").json()
    assert detail["state"] == {
        "completed": True,
        "today_completed": True,
        "favorite": True,
        "started": True,
    }
    assert mini.get("/api/mini/v1/favorites").json()["items"][0]["state"] == detail["state"]


def test_published_admin_preview_never_replaces_it_with_an_unpublished_candidate(admin, mini):
    card = draft(admin)
    publish(admin, card)
    assert (
        admin.put(
            f"/api/admin/v1/cards/{card['id']}",
            headers=key(),
            json={"revision": 1, "content": dict(card["content"], name="未发布的新资料")},
        ).status_code
        == 200
    )
    response = admin.get(f"/api/admin/v1/cards/{card['id']}/published")
    assert response.status_code == 200
    assert response.json()["mode"] == "published"
    assert response.json()["content"]["name"] == "在咖啡店点单"
    assert mini.get("/api/mini/v1/me/statistics").json()["completed_cards"] == 0


def test_settings_representation_does_not_disclose_credentials(system):
    settings = system["settings"]
    assert settings.lookup_key not in repr(settings)
    assert settings.field_encryption_key not in repr(settings)
    assert settings.database_url not in repr(settings)


def test_openapi_operations_have_independent_method_identifiers(system):
    import warnings

    for app in [system["admin"].app, system["mini"].app]:
        with warnings.catch_warnings(record=True) as recorded:
            contract = app.openapi()
        ids = [
            op["operationId"]
            for path in contract["paths"].values()
            for op in path.values()
            if isinstance(op, dict) and "operationId" in op
        ]
        assert len(ids) == len(set(ids))
        assert not recorded


def test_management_list_identifies_published_content_while_editing_a_candidate(admin):
    card = draft(admin)
    publish(admin, card)
    saved = admin.put(
        f"/api/admin/v1/cards/{card['id']}",
        headers=key(),
        json={"revision": 1, "content": dict(card["content"], name="尚未发布的名称")},
    )
    assert saved.status_code == 200
    item = admin.get("/api/admin/v1/cards").json()["items"][0]
    assert item["display_name"] == "在咖啡店点单"
    assert item["content"]["name"] == "尚未发布的名称"


def test_upload_configuration_exposes_actual_environment_limits(admin, system):
    response = admin.get("/api/admin/v1/media/configuration")
    assert response.status_code == 200
    assert response.json()["image_limit_bytes"] == system["settings"].image_limit_mb * 1024 * 1024


def test_mini_configuration_reports_avatar_budget_without_administrator_capabilities(mini, system):
    response = mini.get("/api/mini/v1/configuration")
    assert response.status_code == 200
    assert response.json() == {
        "avatar_limit_bytes": system["settings"].image_limit_mb * 1024 * 1024
    }
    assert mini.get("/api/admin/v1/media/configuration").status_code == 404


def test_published_scene_exposes_inspected_audio_duration_for_native_controls(admin, mini):
    card = draft(admin)
    publish(admin, card)
    duration = admin.get(f"/api/admin/v1/media/{card['content']['audio_id']}/status").json()[
        "duration"
    ]
    assert mini.get(f"/api/mini/v1/cards/{card['id']}").json()["audio_duration"] == duration


def test_unexpected_faults_return_safe_json_without_logging_submitted_personal_values(
    system, mini, monkeypatch, caplog
):
    from starlette.testclient import TestClient

    from juya_api import learning_api

    def fault(*args, **kwargs):
        raise RuntimeError("private-contact-13800138000")

    monkeypatch.setattr(learning_api, "statistics", fault)
    client = TestClient(
        system["mini"].app,
        base_url="https://testserver",
        raise_server_exceptions=False,
        headers=dict(mini.headers),
    )
    response = client.get("/api/mini/v1/me/statistics")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "private-contact-13800138000" not in response.text + caplog.text


def test_administrator_can_query_only_its_own_durable_write_result(admin, mini):
    operation = key()
    created = admin.post(
        "/api/admin/v1/cards", headers=operation, json={"content": {"name": "结果查询测试"}}
    )
    assert created.status_code == 201
    original_key = operation["Idempotency-Key"]
    response = admin.get("/api/admin/v1/operations/" + original_key)
    assert response.status_code == 200
    assert response.json()["result"]["id"] == created.json()["id"]
    assert mini.get("/api/mini/v1/operations/" + original_key).status_code == 404
