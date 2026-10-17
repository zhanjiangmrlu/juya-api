"""Controlled references, shared synthesis, private grants and live revocation."""

from .content_helpers import draft, key, publish, recording


def request_voice(client, card, version, **extra):
    return client.post(
        f"/api/mini/v1/cards/{card}/words/word-1/pronunciation",
        headers=key(),
        json={"version_id": version, **extra},
    )


def test_generation_uses_controlled_text_merges_requests_and_revokes_after_offline(
    admin, mini, system
):
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    first = request_voice(mini, card["id"], version)
    assert first.status_code == 200, first.text
    assert first.json()["state"] == "processing"
    assert request_voice(mini, card["id"], version).json()["job_id"] == first.json()["job_id"]
    assert request_voice(mini, card["id"], version, text="send this instead").status_code == 422
    assert request_voice(mini, card["id"], version, phone="13800138000").status_code == 422
    from juya_api.worker import run_job

    calls = []

    class Provider:
        def synthesize(self, text, configuration, session_id):
            calls.append((text, configuration, session_id))
            return recording()

    run_job(
        system["settings"],
        system["sessions"],
        first.json()["job_id"],
        clock=system["admin"].app.state.clock,
        tts=Provider(),
    )
    response = mini.get(
        f"/api/mini/v1/cards/{card['id']}/words/word-1/pronunciation",
        params={"version_id": version},
    )
    assert response.json()["state"] == "ready", response.text
    assert calls[0][0] == "coffee"
    assert not any(k in calls[0][1] for k in ["user_id", "meaning", "phonetic", "phone", "wechat"])
    url = response.json()["url"]
    assert mini.get(url, headers={"Range": "bytes=0-15"}).status_code == 206
    admin.post(f"/api/admin/v1/cards/{card['id']}/offline", headers=key(), json={"revision": 1})
    assert mini.get(url).status_code == 410
    assert request_voice(mini, card["id"], version).status_code == 410


def test_cache_separates_confirmed_reading_and_preview_revision(admin, system):
    card = draft(admin)
    path = f"/api/admin/v1/cards/{card['id']}/words/word-1/pronunciation"
    first = admin.post(path, headers=key(), json={"revision": 1})
    assert first.status_code == 200, first.text
    payload = card["content"]
    payload["vocabulary"][0]["pronunciation_text"] = "cof fee"
    changed = admin.put(
        f"/api/admin/v1/cards/{card['id']}", headers=key(), json={"revision": 1, "content": payload}
    )
    assert changed.status_code == 200
    assert admin.post(path, headers=key(), json={"revision": 1}).status_code == 409
    second = admin.post(path, headers=key(), json={"revision": 2})
    assert second.status_code == 200, second.text
    assert second.json()["job_id"] != first.json()["job_id"]


def test_daily_budget_counts_actual_provider_attempts_and_manual_retry_has_cooldown(
    admin, mini, system
):
    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    system["settings"].tts_daily_budget = 1
    first = request_voice(mini, card["id"], version).json()
    from juya_api.errors import DomainError
    from juya_api.worker import run_job

    class Provider:
        calls = 0

        def synthesize(self, *_):
            self.calls += 1
            raise DomainError(503, "tts_temporary", "发音暂不可用")

    provider = Provider()
    run_job(
        system["settings"],
        system["sessions"],
        first["job_id"],
        clock=system["admin"].app.state.clock,
        tts=provider,
    )
    from datetime import timedelta

    system["time"][0] += timedelta(seconds=11)
    run_job(
        system["settings"],
        system["sessions"],
        first["job_id"],
        clock=system["admin"].app.state.clock,
        tts=provider,
    )
    assert provider.calls == 1
    state = mini.get(
        f"/api/mini/v1/cards/{card['id']}/words/word-1/pronunciation",
        params={"version_id": version},
    ).json()
    assert state["state"] == "failed" and state["error_code"] == "tts_budget_exceeded"
    assert request_voice(mini, card["id"], version).status_code == 429


def test_real_mysql_different_learners_merge_the_same_synthesis(admin, system):
    import pytest

    if system["engine"].dialect.name != "mysql":
        pytest.skip("Real MySQL cache reservation concurrency")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from fastapi.testclient import TestClient

    card = draft(admin)
    version = publish(admin, card)["current_version_id"]
    tokens = []
    for index in range(4):
        login = (
            system["mini"]
            .post(
                "/api/mini/v1/auth/wechat",
                headers=key(),
                json={
                    "code": f"voice-{index}:first",
                    "consent": True,
                    "consent_version": "2026-10-17",
                },
            )
            .json()
        )
        tokens.append(login["access_token"])
    barrier = Barrier(4)

    def attempt(token):
        with TestClient(system["mini"].app, base_url="https://testserver") as client:
            client.headers["Authorization"] = "Bearer " + token
            barrier.wait()
            return request_voice(client, card["id"], version)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, tokens))
    assert [r.status_code for r in results] == [200] * 4
    assert len({r.json()["job_id"] for r in results}) == 1


def test_synthesis_codec_is_part_of_the_actual_server_configuration_and_cache(admin, system):
    card = draft(admin)
    path = f"/api/admin/v1/cards/{card['id']}/words/word-1/pronunciation"
    first = admin.post(path, headers=key(), json={"revision": 1}).json()
    system["settings"].tts_codec = "wav"
    second = admin.post(path, headers=key(), json={"revision": 1}).json()
    assert second["job_id"] != first["job_id"]
