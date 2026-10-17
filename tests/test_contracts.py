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
    listed = mini.get("/api/mini/v1/cards").json()["items"][0]
    detail = mini.get(f"/api/mini/v1/cards/{card['id']}").json()
    assert listed["state"] == {"completed": True, "today_completed": True, "favorite": True}
    assert detail["state"] == listed["state"]
    assert mini.get("/api/mini/v1/favorites").json()["items"][0]["state"] == listed["state"]


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
