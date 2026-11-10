"""Legacy database fixtures: retirement must not depend on current response contracts."""

import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import event, select

from juya_api.access_models import LearningAuthorization
from juya_api.config import Settings
from juya_api.content_models import Operation
from juya_api.database import make_database
from juya_api.learning_models import Checkin
from juya_api.models import Consent, LoginOperation, MiniSession, User
from juya_api.security import decrypt, encrypt

TABLES = (User, Operation, LoginOperation, Consent, LearningAuthorization, Checkin, MiniSession)
CONTACT_KEYS = ("phone", "wechat_contact", "phone_source", "wechat_source", "contact_version")
NOW = datetime(2026, 11, 1, 1, 2, 3)


def cleanup(sessions, settings, **kwargs):
    try:
        from juya_api.contact_cleanup import clean_contact_data
    except ImportError:
        pytest.fail("The historical contact cleanup implementation is missing")
    return clean_contact_data(sessions, settings, **kwargs)


@pytest.fixture
def legacy(tmp_path):
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'legacy.db'}",
        field_encryption_key="yK1Xc0sWCxUQxXvHPEgY46iVE1mW6BwJqHWSeg1oEJ4=",
        lookup_key="isolated-contact-cleanup-lookup-key",
    )
    engine, sessions = make_database(settings)
    for model in TABLES:
        model.__table__.create(engine)
    profile = {
        "id": "legacy-user",
        "nickname": "旧昵称",
        "avatar_id": "avatar-1",
        "profile_version": 8,
        "phone": "13800000000",
        "wechat_contact": "legacy_wechat",
        "phone_source": "user_entered_unverified",
        "wechat_source": "user_entered_unverified",
        "contact_version": 7,
    }
    with sessions.begin() as db:
        db.execute(
            User.__table__.insert().values(
                id="legacy-user",
                user_number=42,
                app_id="legacy-app",
                openid_digest="identity-digest",
                nickname="旧昵称",
                avatar_id="avatar-1",
                profile_version=8,
                contact_version=7,
                phone_cipher=encrypt(settings, profile["phone"]),
                phone_digest="phone-digest",
                phone_source="user_entered_unverified",
                wechat_cipher=encrypt(settings, "legacy_wechat"),
                wechat_digest="wechat-digest",
                wechat_source="user_entered_unverified",
                registered_at=NOW,
                last_login_at=NOW,
                profile_updated_at=NOW,
                contact_updated_at=NOW,
            )
        )
        for key, action in (
            ("contact", "contact.save"),
            ("profile", "profile.save"),
            ("other", "favorite.save"),
        ):
            db.execute(
                Operation.__table__.insert().values(
                    scope="mini:legacy-user",
                    key_digest=key,
                    action=action,
                    fingerprint=f"fingerprint-{key}",
                    result=encrypt(settings, json.dumps(profile)),
                    accepted_at=NOW,
                )
            )
        for key, expiry in (
            ("expired", NOW - timedelta(days=1)),
            ("current", NOW + timedelta(days=30)),
        ):
            db.execute(
                LoginOperation.__table__.insert().values(
                    key_digest=key,
                    fingerprint=f"login-{key}",
                    expires_at=expiry,
                    result_cipher=encrypt(
                        settings,
                        json.dumps(
                            {
                                "access_token": "fixture-only-token",
                                "user": profile,
                                "expires_in": 604800,
                            }
                        ),
                    ),
                )
            )
        for purpose in ("contact.phone", "contact.wechat", "privacy", "learning"):
            db.execute(
                Consent.__table__.insert().values(
                    id=purpose,
                    user_id="legacy-user",
                    purpose=purpose,
                    version="v1",
                    accepted_at=NOW,
                )
            )
        db.execute(
            LearningAuthorization.__table__.insert().values(
                user_id="legacy-user",
                starts_on=date(2026, 10, 1),
                expires_on=date(2027, 1, 1),
                revision=9,
            )
        )
        db.execute(
            Checkin.__table__.insert().values(
                user_id="legacy-user",
                date=date(2026, 11, 1),
                accepted_at=NOW,
            )
        )
        db.execute(
            MiniSession.__table__.insert().values(
                token_digest="session-digest",
                user_id="legacy-user",
                expires_at=NOW + timedelta(days=7),
            )
        )
    yield settings, sessions, engine
    engine.dispose()


def snapshot(sessions):
    with sessions() as db:
        return {
            model.__tablename__: list(db.execute(select(model.__table__)).mappings())
            for model in TABLES
        }


def test_dry_run_reports_candidates_without_changing_any_persisted_bytes(legacy):
    settings, sessions, _ = legacy
    before = snapshot(sessions)
    counts = cleanup(sessions, settings, batch_size=1)
    assert counts["status"] == "dry_run"
    assert counts["users_cleared"] == 1
    assert counts["contact_operations_deleted"] == 1
    assert counts["contact_consents_deleted"] == 2
    assert counts["profile_receipts_cleaned"] == 1
    assert counts["login_receipts_cleaned"] == 2
    assert snapshot(sessions) == before


def test_apply_cleans_all_receipts_and_retains_identity_authorization_and_learning(legacy):
    settings, sessions, _ = legacy
    before = snapshot(sessions)
    counts = cleanup(sessions, settings, apply=True, batch_size=1)
    assert counts["status"] == "complete"
    after = snapshot(sessions)
    expected_user = dict(before["users"][0])
    for key in (
        "phone_cipher",
        "phone_digest",
        "phone_source",
        "wechat_cipher",
        "wechat_digest",
        "wechat_source",
        "contact_updated_at",
    ):
        expected_user[key] = None
    assert after["users"] == [expected_user]
    for table in ("learning_authorizations", "checkins", "mini_sessions"):
        assert after[table] == before[table]
    assert {row["purpose"] for row in after["consents"]} == {"privacy", "learning"}
    assert {row["action"] for row in after["operations"]} == {"profile.save", "favorite.save"}
    original_profile = next(row for row in before["operations"] if row["action"] == "profile.save")
    cleaned_profile = next(row for row in after["operations"] if row["action"] == "profile.save")
    assert {k: v for k, v in cleaned_profile.items() if k != "result"} == {
        k: v for k, v in original_profile.items() if k != "result"
    }
    profile = json.loads(decrypt(settings, cleaned_profile["result"]))
    assert profile == {
        "id": "legacy-user",
        "nickname": "旧昵称",
        "avatar_id": "avatar-1",
        "profile_version": 8,
    }
    for row in after["login_operations"]:
        old = next(
            old for old in before["login_operations"] if old["key_digest"] == row["key_digest"]
        )
        assert {k: v for k, v in row.items() if k != "result_cipher"} == {
            k: v for k, v in old.items() if k != "result_cipher"
        }
        assert json.loads(decrypt(settings, row["result_cipher"])) == {
            "access_token": "fixture-only-token",
            "expires_in": 604800,
            "user": profile,
        }
    other = next(row for row in after["operations"] if row["action"] == "favorite.save")
    assert other == next(row for row in before["operations"] if row["action"] == "favorite.save")
    again = cleanup(sessions, settings, apply=True, batch_size=2)
    assert again["status"] == "complete"
    assert all(
        again[key] == 0
        for key in (
            "users_cleared",
            "contact_operations_deleted",
            "contact_consents_deleted",
            "profile_receipts_cleaned",
            "login_receipts_cleaned",
        )
    )
    assert snapshot(sessions) == after


def test_failed_batch_rolls_back_and_can_be_retried_without_secret_output(legacy, capsys):
    settings, sessions, engine = legacy
    with sessions.begin() as db:
        db.add(
            LoginOperation(
                key_digest="zzz-corrupt",
                fingerprint="unchanged",
                result_cipher="PRIVATE-CORRUPT",
                expires_at=NOW,
            )
        )
    before_logins = snapshot(sessions)["login_operations"]
    counts = cleanup(sessions, settings, apply=True, batch_size=100)
    assert counts["status"] == "incomplete"
    assert counts["receipt_failures"] == 1
    assert counts["failed_batches"] == 1
    assert counts["login_receipts_cleaned"] == 0
    assert snapshot(sessions)["login_operations"] == before_logins
    assert "PRIVATE-CORRUPT" not in repr(counts) + capsys.readouterr().out
    with sessions.begin() as db:
        db.get(LoginOperation, "zzz-corrupt").result_cipher = encrypt(settings, '{"user": {}}')
    assert cleanup(sessions, settings, apply=True)["status"] == "complete"
    assert engine.dialect.name == "sqlite"


def test_database_write_failure_rolls_back_whole_batch_then_retry_succeeds(legacy):
    settings, sessions, engine = legacy
    before_all = snapshot(sessions)
    before = before_all["users"]

    def reject_user_update(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE users"):
            raise RuntimeError("PRIVATE-DATABASE-ERROR")

    event.listen(engine, "before_cursor_execute", reject_user_update)
    try:
        counts = cleanup(sessions, settings, apply=True)
    finally:
        event.remove(engine, "before_cursor_execute", reject_user_update)
    assert counts["status"] == "incomplete"
    assert counts["failed_batches"] == 1
    assert counts["users_cleared"] == 0
    assert "PRIVATE-DATABASE-ERROR" not in repr(counts)
    assert snapshot(sessions)["users"] == before
    assert snapshot(sessions) == before_all
    assert cleanup(sessions, settings, apply=True)["users_cleared"] == 1


@pytest.mark.parametrize("value", ["[]", '{"user": []}'])
def test_unexpected_receipt_shape_is_incomplete_not_silently_completed(legacy, value):
    settings, sessions, _ = legacy
    with sessions.begin() as db:
        db.get(LoginOperation, "current").result_cipher = encrypt(settings, value)
    assert cleanup(sessions, settings, apply=True)["status"] == "incomplete"


def test_non_positive_batch_is_rejected_before_writes(legacy):
    settings, sessions, _ = legacy
    before = snapshot(sessions)
    with pytest.raises(ValueError):
        cleanup(sessions, settings, apply=True, batch_size=0)
    assert snapshot(sessions) == before


def test_cli_requires_matching_explicit_target_and_defaults_to_dry_run(legacy, tmp_path):
    settings, sessions, engine = legacy
    config = tmp_path / "private.env"
    config.write_text(
        f"JUYA_ENVIRONMENT=test\nJUYA_DATABASE_URL={settings.database_url}\n"
        f"JUYA_FIELD_ENCRYPTION_KEY={settings.field_encryption_key}\n"
        f"JUYA_LOOKUP_KEY={settings.lookup_key}\n"
    )
    config.chmod(0o600)
    script = Path(__file__).resolve().parents[1] / "scripts" / "cleanup-contact-data.py"
    args = [
        sys.executable,
        str(script),
        "--config",
        str(config),
        "--environment",
        "test",
        "--database-host",
        "local-file",
        "--database-name",
        str(engine.url.database),
    ]
    before = snapshot(sessions)
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "dry_run"
    assert snapshot(sessions) == before
    result = subprocess.run([*args[:-1], "wrong-target", "--apply"], capture_output=True, text=True)
    assert result.returncode != 0
    assert snapshot(sessions) == before
    assert settings.field_encryption_key not in result.stdout + result.stderr
    result = subprocess.run([*args, "--apply"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "complete"
    assert snapshot(sessions)["users"][0]["phone_cipher"] is None


def test_receipt_failure_stops_later_batches_until_explicit_retry(legacy):
    settings, sessions, _ = legacy
    with sessions.begin() as db:
        db.get(LoginOperation, "current").result_cipher = "INVALID-PRIVATE"
    before = snapshot(sessions)["login_operations"]
    counts = cleanup(sessions, settings, apply=True, batch_size=1)
    assert counts["status"] == "incomplete"
    assert counts["login_receipts_cleaned"] == 0
    assert snapshot(sessions)["login_operations"] == before


def test_prior_successful_batch_survives_failure_and_only_remaining_rows_retry(legacy):
    settings, sessions, engine = legacy
    original = dict(snapshot(sessions)["users"][0])
    original.update(id="zzz-user", user_number=43, openid_digest="second-identity")
    with sessions.begin() as db:
        db.execute(User.__table__.insert().values(original))

    def reject_second_update(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE users") and "zzz-user" in parameters:
            raise RuntimeError("isolated-write-failure")

    event.listen(engine, "before_cursor_execute", reject_second_update)
    try:
        counts = cleanup(sessions, settings, apply=True, batch_size=1)
    finally:
        event.remove(engine, "before_cursor_execute", reject_second_update)
    assert counts["status"] == "incomplete"
    assert counts["users_cleared"] == 1
    users = {row["id"]: row for row in snapshot(sessions)["users"]}
    assert users["legacy-user"]["phone_cipher"] is None
    assert users["zzz-user"] == original
    retry = cleanup(sessions, settings, apply=True, batch_size=1)
    assert retry["status"] == "complete"
    assert retry["users_cleared"] == 1


def test_dry_run_never_issues_data_mutation_sql(legacy):
    settings, sessions, engine = legacy

    def reject_dml(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().split()[0].upper() in {"UPDATE", "DELETE", "INSERT"}:
            raise RuntimeError("dry-run-must-not-write")

    event.listen(engine, "before_cursor_execute", reject_dml)
    try:
        assert cleanup(sessions, settings)["status"] == "dry_run"
    finally:
        event.remove(engine, "before_cursor_execute", reject_dml)


def test_empty_login_receipt_is_preserved_and_other_login_receipts_are_cleaned(legacy):
    settings, sessions, _ = legacy
    with sessions.begin() as db:
        db.get(LoginOperation, "current").result_cipher = ""
    counts = cleanup(sessions, settings, apply=True)
    assert counts["status"] == "complete"
    assert counts["login_receipts_cleaned"] == 1
    with sessions() as db:
        assert db.get(LoginOperation, "current").result_cipher == ""
