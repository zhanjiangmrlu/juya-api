"""CHG-0040 separates necessary identity, agreements and optional analysis."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select

from juya_api.models import Consent, User

P = "/api/mini/v1"
DOCS = [
    dict(kind=k, version="v1", title=k, content="已确认的隔离测试正文 " + k)
    for k in ("terms", "privacy", "analytics")
]


def published(system):
    system["mini"].app.state.privacy_documents = DOCS


def confirmation(**changes):
    return dict(
        confirmation_id=str(uuid4()),
        terms_version="v1",
        privacy_version="v1",
        client_confirmed_at="2026-10-17T07:59:00Z",
        source="first_entry",
        **changes,
    )


def login(system, confirm=None, choice=None):
    body = dict(code="alice:privacy", consent=True, consent_version="2026-10-17")
    if confirm:
        body["agreement_confirmation"] = confirm
    if choice is not None:
        body["analytics_choice"] = choice
    return system["mini"].post(
        P + "/auth/wechat", json=body, headers={"Idempotency-Key": str(uuid4())}
    )


def test_legacy_policies_are_public_and_never_create_accounts(system):
    response = system["mini"].get(P + "/privacy/policies")
    assert response.status_code == 200
    assert response.json()["mode"] == "legacy"
    assert response.json()["documents"] == []
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0


def test_published_requires_both_current_agreements_before_wechat(system):
    published(system)
    response = login(system)
    assert response.status_code == 409
    assert system["wechat"].calls == 0
    response = login(system, confirmation())
    assert response.status_code == 200, response.text
    assert system["wechat"].calls == 1


def test_confirmation_is_durable_and_repeated_login_does_not_duplicate(system):
    published(system)
    value = confirmation()
    first = login(system, value)
    second = login(system, value)
    assert first.status_code == second.status_code == 200
    assert first.json()["user"]["id"] == second.json()["user"]["id"]
    with system["sessions"]() as db:
        records = list(db.scalars(select(Consent).where(Consent.purpose.in_(["terms", "privacy"]))))
        assert len(records) == 2
        assert {r.source for r in records} == {"first_entry"}
        assert {r.confirmation_id for r in records} == {value["confirmation_id"]}


def test_stale_analytics_disclosure_does_not_break_necessary_login(system):
    published(system)
    response = login(system, confirmation(), {"enabled": True, "scope_version": "old"})
    assert response.status_code == 200
    client = system["mini"]
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    state = client.get(P + "/me/privacy")
    assert state.status_code == 200
    assert state.json()["analytics"]["enabled"] is False
    assert state.json()["analytics"]["collecting"] is False


def test_only_login_does_not_inherit_previous_account_permission(system):
    published(system)
    response = login(system, confirmation(), {"enabled": False, "scope_version": "v1"})
    client = system["mini"]
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    state = client.get(P + "/me/privacy").json()
    assert state["analytics"]["enabled"] is False
    assert state["agreements"]["current"] is True


def test_preference_has_cas_persistent_idempotency_and_immediate_withdrawal(mini, system):
    published(system)
    mini.post(P + "/me/agreements", json=confirmation(), headers={"Idempotency-Key": str(uuid4())})
    body = {"enabled": True, "scope_version": "v1", "expected_revision": 0}
    key = {"Idempotency-Key": str(uuid4())}
    response = mini.put(P + "/me/analytics-preference", json=body, headers=key)
    assert response.status_code == 200, response.text
    assert response.json()["enabled"] is True
    assert response.json()["collecting"] is False
    assert (
        mini.put(P + "/me/analytics-preference", json=body, headers=key).json() == response.json()
    )
    assert (
        mini.put(
            P + "/me/analytics-preference", json=body, headers={"Idempotency-Key": str(uuid4())}
        ).status_code
        == 409
    )
    off = mini.put(
        P + "/me/analytics-preference",
        json={"enabled": False, "scope_version": "v1", "expected_revision": 1},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert off.status_code == 200
    assert off.json()["enabled"] is False
    assert off.json()["revision"] == 2


def test_default_runtime_rejects_events_without_collecting_even_if_permission_exists(mini, system):
    published(system)
    mini.post(P + "/me/agreements", json=confirmation(), headers={"Idempotency-Key": str(uuid4())})
    mini.put(
        P + "/me/analytics-preference",
        json={"enabled": True, "scope_version": "v1", "expected_revision": 0},
        headers={"Idempotency-Key": str(uuid4())},
    )
    response = mini.post(
        P + "/analytics/events",
        json={
            "event_id": str(uuid4()),
            "event": "page_enter",
            "occurred_at": "2026-10-17T08:00:00Z",
            "consent_revision": 1,
            "properties": {"page_path": "pages/home/index"},
        },
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "analytics_unavailable"


def test_isolated_receiver_validates_generation_identity_and_event_deduplication(mini, system):
    published(system)
    system["mini"].app.state.analytics_receiver = lambda event: None
    mini.post(P + "/me/agreements", json=confirmation(), headers={"Idempotency-Key": str(uuid4())})
    mini.put(
        P + "/me/analytics-preference",
        json={"enabled": True, "scope_version": "v1", "expected_revision": 0},
        headers={"Idempotency-Key": str(uuid4())},
    )
    value = {
        "event_id": str(uuid4()),
        "event": "page_enter",
        "occurred_at": "2026-10-17T08:00:00Z",
        "consent_revision": 1,
        "properties": {"page_path": "pages/home/index"},
    }
    response = mini.post(P + "/analytics/events", json=value)
    assert response.status_code == 200, response.text
    assert mini.post(P + "/analytics/events", json=value).json() == response.json()
    assert (
        mini.post(
            P + "/analytics/events", json={**value, "properties": {"page_path": "other"}}
        ).status_code
        == 409
    )
    assert (
        mini.post(
            P + "/analytics/events", json={**value, "event_id": str(uuid4()), "user_id": "other"}
        ).status_code
        == 422
    )
    assert (
        mini.post(
            P + "/analytics/events",
            json={**value, "event_id": str(uuid4()), "event": "login_success"},
        ).status_code
        == 422
    )
    mini.put(
        P + "/me/analytics-preference",
        json={"enabled": False, "scope_version": "v1", "expected_revision": 1},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert (
        mini.post(P + "/analytics/events", json={**value, "event_id": str(uuid4())}).status_code
        == 403
    )
    with system["sessions"]() as db:
        from juya_api.privacy_models import AnalyticsEventReceipt

        assert db.scalar(select(func.count()).select_from(AnalyticsEventReceipt)) == 1


def test_policy_detail_is_versioned_and_expired_session_cannot_change_permission(mini, system):
    published(system)
    assert mini.get(P + "/privacy/policies/terms?version=v1").status_code == 200
    assert mini.get(P + "/privacy/policies/terms?version=old").status_code == 404
    system["time"][0] += timedelta(days=8)
    assert (
        mini.put(
            P + "/me/analytics-preference",
            json={"enabled": False, "scope_version": "", "expected_revision": 0},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 401
    )


def test_replaced_disclosure_makes_existing_permission_effectively_off(mini, system):
    published(system)
    mini.post(P + "/me/agreements", json=confirmation(), headers={"Idempotency-Key": str(uuid4())})
    mini.put(
        P + "/me/analytics-preference",
        json={"enabled": True, "scope_version": "v1", "expected_revision": 0},
        headers={"Idempotency-Key": str(uuid4())},
    )
    system["mini"].app.state.privacy_documents = [
        {**v, "version": "v2"} if v["kind"] == "analytics" else v for v in DOCS
    ]
    assert mini.get(P + "/me/privacy").json()["analytics"]["enabled"] is False


def test_unauthenticated_cannot_read_or_write_account_permission(system):
    client = system["mini"]
    assert client.get(P + "/me/privacy").status_code == 401
    assert (
        client.post(
            P + "/me/agreements", json=confirmation(), headers={"Idempotency-Key": str(uuid4())}
        ).status_code
        == 401
    )


def test_invalid_config_never_publishes_half_a_policy(system):
    system["mini"].app.state.privacy_documents = DOCS[:1]
    assert system["mini"].get(P + "/privacy/policies").json()["mode"] == "legacy"


def test_receiver_rejects_input_disguised_as_page_or_result(mini, system):
    published(system)
    mini.app.state.analytics_receiver = lambda event: None
    mini.post(P + "/me/agreements", json=confirmation(), headers={"Idempotency-Key": str(uuid4())})
    mini.put(
        P + "/me/analytics-preference",
        json={"enabled": True, "scope_version": "v1", "expected_revision": 0},
        headers={"Idempotency-Key": str(uuid4())},
    )
    event = {
        "event_id": str(uuid4()),
        "event": "page_enter",
        "occurred_at": "2026-10-17T08:00:00Z",
        "consent_revision": 1,
        "properties": {"page_path": "pages/private-user-input"},
    }
    assert mini.post(P + "/analytics/events", json=event).status_code == 422
    event["properties"] = {"page_path": "pages/home/index", "audio_kind": "private text"}
    assert mini.post(P + "/analytics/events", json=event).status_code == 422
    event["event"] = "content_open"
    event["properties"] = {
        "page_path": "private input",
        "content_type": "scene",
        "content_id": "missing",
    }
    assert mini.post(P + "/analytics/events", json=event).status_code == 422


def test_updated_necessary_agreement_hides_old_effective_permission(mini, system):
    published(system)
    mini.post(P + "/me/agreements", json=confirmation(), headers={"Idempotency-Key": str(uuid4())})
    mini.put(
        P + "/me/analytics-preference",
        json={"enabled": True, "scope_version": "v1", "expected_revision": 0},
        headers={"Idempotency-Key": str(uuid4())},
    )
    mini.app.state.privacy_documents = [
        {**v, "version": "v2"} if v["kind"] == "terms" else v for v in DOCS
    ]
    state = mini.get(P + "/me/privacy").json()
    assert state["agreements"]["current"] is False
    assert state["analytics"]["enabled"] is False


def test_content_and_business_events_require_real_success_without_changing_grades(
    admin, mini, system
):
    from tests.test_learning import scene

    card, version = scene(admin)
    published(system)
    received = []
    mini.app.state.analytics_receiver = received.append
    mini.post(P + "/me/agreements", json=confirmation(), headers={"Idempotency-Key": str(uuid4())})
    mini.put(
        P + "/me/analytics-preference",
        json={"enabled": True, "scope_version": "v1", "expected_revision": 0},
        headers={"Idempotency-Key": str(uuid4())},
    )
    props = {"content_type": "scene", "content_id": card["id"], "version_id": version}
    base = {"occurred_at": "2026-10-17T08:00:00Z", "consent_revision": 1}
    for event in ["content_open", "audio_play"]:
        r = mini.post(
            P + "/analytics/events",
            json={**base, "event_id": str(uuid4()), "event": event, "properties": props},
        )
        assert r.status_code == 200, r.text
    unconfirmed = mini.post(
        P + "/analytics/events",
        json={**base, "event_id": str(uuid4()), "event": "learning_complete", "properties": props},
    )
    assert unconfirmed.status_code == 403
    for event, method, path, result in [
        ("favorite_change", "PUT", "favorite", {"favorite": 1}),
        ("learning_complete", "POST", "complete", {}),
    ]:
        key = str(uuid4())
        response = mini.request(
            method,
            P + "/cards/" + card["id"] + "/" + path,
            json={"version_id": version},
            headers={"Idempotency-Key": key},
        )
        assert response.status_code == 200, response.text
        before = mini.get(P + "/me/statistics").json()
        payload = {
            **base,
            "event_id": str(uuid4()),
            "event": event,
            "properties": {**props, **result},
            "operation_key": key,
        }
        accepted = mini.post(P + "/analytics/events", json=payload)
        assert accepted.status_code == 200, accepted.text
        assert mini.post(P + "/analytics/events", json=payload).status_code == 200
        assert mini.get(P + "/me/statistics").json() == before
    assert len(received) == 4
    assert all("operation_key" not in event for event in received)


def test_privacy_responses_are_described_for_generated_clients(system):
    schema = system["mini"].get("/openapi.json").json()
    ref = schema["paths"][P + "/privacy/policies"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert "$ref" in ref
    assert "documents" in schema["components"]["schemas"][ref["$ref"].split("/")[-1]]["properties"]


def test_legacy_client_transport_switch_cannot_bypass_closed_statistics(system, mini):
    """Legacy switches never advertise collection, accept events or create receipts."""
    from juya_api.config import Settings
    from juya_api.privacy_models import AnalyticsEventReceipt

    published(system)
    system["mini"].app.state.settings = Settings.model_validate(
        {**system["settings"].model_dump(), "analytics_client_transport_enabled": True}
    )
    assert system["mini"].get(P + "/privacy/policies").json()["analytics_available"] is False
    mini.post(P + "/me/agreements", json=confirmation(), headers={"Idempotency-Key": str(uuid4())})
    permitted = mini.put(
        P + "/me/analytics-preference",
        json={"enabled": True, "scope_version": "v1", "expected_revision": 0},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert permitted.status_code == 200
    assert permitted.json()["enabled"] is True and permitted.json()["collecting"] is False
    event = {
        "event_id": str(uuid4()),
        "event": "page_enter",
        "occurred_at": system["time"][0].isoformat(),
        "consent_revision": 1,
        "properties": {"page_path": "pages/home/index"},
    }
    assert mini.post(P + "/analytics/events", json=event).status_code == 503
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(AnalyticsEventReceipt)) == 0


def test_configured_release_documents_are_readable_anonymously_without_creating_users(system):
    """The versioned release bundle is complete and all three documents are public."""
    from pathlib import Path

    from juya_api.privacy_service import load_documents

    configured = system["settings"].model_copy(
        update={
            "privacy_documents_path": Path(__file__).parents[1]
            / "src/juya_api/policies/chg0040-20261110-v1.json"
        }
    )
    system["mini"].app.state.privacy_documents = load_documents(configured)
    catalog = system["mini"].get(P + "/privacy/policies").json()
    assert catalog["mode"] == "published"
    assert {d["kind"] for d in catalog["documents"]} == {"terms", "privacy", "analytics"}
    for document in catalog["documents"]:
        response = system["mini"].get(
            P + "/privacy/policies/" + document["kind"] + "?version=" + document["version"]
        )
        assert response.status_code == 200
        assert response.json() == document
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0


def test_client_sdk_test_transport_cannot_be_enabled_in_production(system):
    """The new test capability cannot implicitly turn on an existing production service."""
    import pytest
    from pydantic import ValidationError

    from juya_api.config import Settings

    values = {
        **system["settings"].model_dump(),
        "environment": "production",
        "database_url": "mysql+pymysql://fixture:fixture@mysql/juya_production",
        "storage_backend": "oss",
        "wechat_app_secret": "fixture",
        "analytics_client_transport_enabled": True,
    }
    with pytest.raises(ValidationError, match="not enabled for production"):
        Settings.model_validate(values)
