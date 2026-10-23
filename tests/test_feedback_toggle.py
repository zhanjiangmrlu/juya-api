"""Safety is optional by default; authentication and content validation remain enforced."""

import pytest

from .content_helpers import key, picture
from .test_feedback import ADMIN, MINI, UnavailableContent


def test_feedback_safety_defaults_off_and_environment_enables(monkeypatch, system):
    from juya_api.config import Settings

    monkeypatch.delenv("JUYA_FEEDBACK_SAFETY_ENABLED", raising=False)
    values = {
        name: getattr(system["settings"], name)
        for name in ["database_url", "lookup_key", "field_encryption_key"]
    }
    assert Settings(_env_file=None, **values).feedback_safety_enabled is False
    monkeypatch.setenv("JUYA_FEEDBACK_SAFETY_ENABLED", "true")
    assert Settings(_env_file=None, **values).feedback_safety_enabled is True


@pytest.mark.parametrize("enabled", [False, True])
def test_toggle_covers_create_append_image_and_admin_reply(mini, admin, enabled):
    settings = mini.app.state.settings
    # Establish a thread before the unavailable provider is selected.
    mini.app.state.feedback_safety = UnavailableContent()
    admin.app.state.feedback_safety = UnavailableContent()
    settings.feedback_safety_enabled = False
    created = mini.post(
        MINI, headers=key(), json={"source": "profile", "category": "content", "text": "有效反馈"}
    )
    assert created.status_code == 201, created.text
    settings.feedback_safety_enabled = enabled
    for response, success in [
        (
            mini.post(
                MINI,
                headers=key(),
                json={"source": "profile", "category": "display", "text": "另一条反馈"},
            ),
            201,
        ),
        (
            mini.post(
                MINI + "/" + created.json()["id"] + "/messages",
                headers=key(),
                json={"text": "追加说明"},
            ),
            200,
        ),
        (
            mini.post(
                MINI + "/images",
                headers=key(),
                files={"file": ("screen.png", picture(), "image/png")},
            ),
            201,
        ),
        (
            admin.post(
                ADMIN + "/" + created.json()["id"] + "/messages",
                headers=key(),
                json={"text": "管理员回复"},
            ),
            200,
        ),
    ]:
        assert response.status_code == (503 if enabled else success), response.text
    assert (
        mini.post(
            MINI, headers=key(), json={"source": "profile", "category": "content", "text": " "}
        ).status_code
        == 422
    )
    assert (
        mini.post(
            MINI + "/images", headers=key(), files={"file": ("bad.png", b"invalid", "image/png")}
        ).status_code
        == 422
    )
    assert (
        admin.post(
            ADMIN + "/" + created.json()["id"] + "/messages",
            headers={**key(), "X-CSRF-Token": "wrong"},
            json={"text": "管理员回复"},
        ).status_code
        == 403
    )
