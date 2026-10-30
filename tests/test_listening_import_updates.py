"""Explicit batch updates preserve published snapshots and stable learning identities."""

import io
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from tests.content_helpers import key, picture, recording
from tests.test_listening import A, M, article, policy, post, publish, topic
from tests.test_listening_imports import assign, document, package, upload


def staged(admin, title="新的听读资料"):
    return upload(admin, post(admin, A + "/imports", {"mode": "zip"}), package(title))


def bind(admin, batch, candidate_id, target, *, payload=None, topic_id=None):
    candidate = next(c for c in batch["candidates"] if c["id"] == candidate_id)
    response = admin.put(
        A + f"/imports/{batch['id']}/candidates/{candidate_id}",
        headers=key(),
        json={
            "revision": batch["revision"],
            "topic_id": topic_id or target["topic_id"],
            "payload": payload or candidate["payload"],
            "target_article_id": target["id"],
            "target_revision": target["revision"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def confirm(admin, batch, ids=None):
    return post(
        admin,
        A + f"/imports/{batch['id']}/preview",
        {
            "revision": batch["revision"],
            "candidate_ids": ids or [c["id"] for c in batch["candidates"]],
        },
    )


def test_batch_update_waits_for_confirmation_and_preserves_live_version_history_and_timeline(
    admin, mini, system
):
    from juya_api.listening_models import ListeningJob

    target = publish(admin, article(admin))
    old_payload, old_version = target["payload"], target["version_id"]
    policy(admin, 1)
    post(mini, M + f"/articles/{target['id']}/complete", {"version_id": old_version})
    assert (
        mini.put(
            M + f"/articles/{target['id']}/favorite",
            headers=key(),
            json={"version_id": old_version},
        ).status_code
        == 200
    )
    batch = staged(admin)
    cid = batch["candidates"][0]["id"]
    new_topic = topic(admin)
    batch = bind(admin, batch, cid, target, topic_id=new_topic["id"])
    candidate = batch["candidates"][0]
    assert candidate["target_article_id"] == target["id"]
    assert candidate["target_revision"] == target["revision"]
    assert "_metadata" not in candidate["resources"]
    restored = admin.get(A + f"/imports/{batch['id']}").json()
    assert restored["candidates"][0]["target_article_id"] == target["id"]
    assert admin.get(A + f"/articles/{target['id']}").json()["revision"] == target["revision"]
    preview = confirm(admin, batch)
    assert preview["changes"] == [
        {
            "candidate_id": cid,
            "operation": "update",
            "target_article_id": target["id"],
            "target_revision": target["revision"],
            "before": {"topic_id": target["topic_id"], "payload": old_payload},
            "after": {"topic_id": new_topic["id"], "payload": candidate["payload"]},
        }
    ]
    assert admin.get(A + f"/articles/{target['id']}").json()["payload"] == old_payload
    with system["sessions"]() as db:
        before_jobs = db.scalar(select(func.count()).select_from(ListeningJob))
    headers = key()
    path = A + f"/imports/{batch['id']}/save"
    saved = admin.post(path, headers=headers, json={"preview_token": preview["preview_token"]})
    assert saved.status_code == 200, saved.text
    assert (
        admin.post(path, headers=headers, json={"preview_token": preview["preview_token"]}).json()
        == saved.json()
    )
    assert saved.json()["items"] == [
        {
            "candidate_id": cid,
            "status": "success",
            "article_id": target["id"],
            "error": None,
            "published_version_id": None,
        }
    ]
    actual = admin.get(A + f"/articles/{target['id']}").json()
    assert actual["revision"] == target["revision"] + 1 and actual["version_id"] == old_version
    assert actual["payload"] == candidate["payload"] and actual["batch_id"] == target["batch_id"]
    assert admin.get(A + "/articles").json()["total"] == 1
    assert (
        admin.get(A + "/articles", params={"batch_id": batch["id"]}).json()["items"][0]["id"]
        == target["id"]
    )
    live = mini.get(M + f"/articles/{target['id']}").json()
    assert live["payload"] == old_payload and live["topic_id"] == target["topic_id"]
    assert live["state"]["favorite"] and live["state"]["completed"]
    assert mini.get(M + "/statistics").json()["completed_articles"] == 1
    assert actual["timeline"]["job_id"] == candidate["timeline"]["job_id"]
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(ListeningJob)) == before_jobs
    # Saved candidate grants survive normal editing without allowing arbitrary batch media.
    edited = admin.put(
        A + f"/articles/{target['id']}",
        headers=key(),
        json={
            "revision": actual["revision"],
            "topic_id": actual["topic_id"],
            "payload": actual["payload"],
        },
    )
    assert edited.status_code == 200, edited.text
    assert (
        admin.get(A + f"/articles/{target['id']}/media/{actual['payload']['audio_id']}").status_code
        == 200
    )


def test_staging_can_keep_only_bound_targets_selected_original_media(admin):
    target = article(admin)
    image = admin.post(
        A + f"/articles/{target['id']}/media?kind=image",
        headers=key(),
        files={"file": ("target.png", picture(), "image/png")},
    ).json()
    target = admin.put(
        A + f"/articles/{target['id']}",
        headers=key(),
        json={
            "revision": target["revision"],
            "topic_id": target["topic_id"],
            "payload": {**target["payload"], "image_id": image["id"]},
        },
    ).json()
    unrelated = article(admin)
    batch = staged(admin)
    cid = batch["candidates"][0]["id"]
    original_staged = batch["candidates"][0]["payload"]
    kept = {**original_staged, "audio_id": target["payload"]["audio_id"], "image_id": image["id"]}
    batch = bind(admin, batch, cid, target, payload=kept)
    for medium_id in [kept["audio_id"], kept["image_id"]]:
        assert admin.get(A + f"/imports/{batch['id']}/media/{medium_id}").status_code == 200
    assert (
        admin.get(
            A + f"/imports/{batch['id']}/media/{unrelated['payload']['audio_id']}"
        ).status_code
        == 404
    )
    batch = bind(admin, batch, cid, target, payload=original_staged)
    assert admin.get(A + f"/imports/{batch['id']}/media/{kept['audio_id']}").status_code == 404
    denied = admin.put(
        A + f"/imports/{batch['id']}/candidates/{cid}",
        headers=key(),
        json={
            "revision": batch["revision"],
            "topic_id": target["topic_id"],
            "target_article_id": target["id"],
            "target_revision": target["revision"],
            "payload": {**kept, "audio_id": unrelated["payload"]["audio_id"]},
        },
    )
    assert denied.status_code == 422


def test_target_conflict_is_per_item_and_only_failed_candidate_is_retried(admin):
    target = article(admin)
    batch = upload(
        admin, post(admin, A + "/imports", {"mode": "zip"}), package("更新甲"), package("新建乙")
    )
    update_id, create_id = [c["id"] for c in batch["candidates"]]
    batch = bind(admin, batch, update_id, target)
    batch = assign(admin, batch, create_id, target["topic_id"])
    preview = confirm(admin, batch)
    externally_edited = admin.put(
        A + f"/articles/{target['id']}",
        headers=key(),
        json={
            "revision": target["revision"],
            "topic_id": target["topic_id"],
            "payload": {**target["payload"], "title_zh": "别人已修改"},
        },
    ).json()
    saved = post(
        admin, A + f"/imports/{batch['id']}/save", {"preview_token": preview["preview_token"]}
    )
    outcomes = {r["candidate_id"]: r for r in saved["items"]}
    assert (
        outcomes[update_id]["status"] == "failed"
        and outcomes[update_id]["error"] == "listening_article_changed"
    )
    assert outcomes[create_id]["status"] == "success"
    assert admin.get(A + f"/articles/{target['id']}").json()["payload"]["title_zh"] == "别人已修改"
    batch = bind(admin, saved["batch"], update_id, externally_edited)
    retried = post(
        admin,
        A + f"/imports/{batch['id']}/save",
        {"preview_token": confirm(admin, batch, [update_id])["preview_token"]},
    )
    assert retried["items"][0]["article_id"] == target["id"]
    assert admin.get(A + "/articles").json()["total"] == 2
    assert len(admin.get(A + "/articles", params={"batch_id": batch["id"]}).json()["items"]) == 2


def test_deleted_target_fails_without_creating_replacement_and_remove_does_not_touch_target(
    admin, system
):
    from juya_api.listening_models import ListeningArticle

    target = article(admin)
    batch = staged(admin)
    cid = batch["candidates"][0]["id"]
    batch = bind(admin, batch, cid, target)
    preview = confirm(admin, batch)
    post(admin, A + f"/articles/{target['id']}/delete", {"revision": target["revision"]})
    result = post(
        admin, A + f"/imports/{batch['id']}/save", {"preview_token": preview["preview_token"]}
    )
    assert result["items"][0]["error"] == "listening_article_deleted"
    with system["sessions"]() as db:
        assert db.scalar(select(func.count()).select_from(ListeningArticle)) == 1
    removed = post(
        admin,
        A + f"/imports/{batch['id']}/remove",
        {"revision": result["batch"]["revision"], "candidate_ids": [cid]},
    )
    restored = admin.get(A + f"/imports/{batch['id']}").json()
    assert (
        removed["candidates"][0]["removed"]
        and restored["candidates"][0]["target_article_id"] == target["id"]
    )
    assert admin.get(A + f"/articles/{target['id']}").json()["status"] == "deleted"


def test_pair_validation_binding_recovery_and_same_batch_duplicate_target_conflict(admin):
    target = article(admin)
    batch = upload(
        admin, post(admin, A + "/imports", {"mode": "zip"}), package("甲"), package("乙")
    )
    first, second = batch["candidates"]
    invalid = admin.put(
        A + f"/imports/{batch['id']}/candidates/{first['id']}",
        headers=key(),
        json={
            "revision": batch["revision"],
            "topic_id": target["topic_id"],
            "payload": first["payload"],
            "target_article_id": target["id"],
        },
    )
    assert invalid.status_code == 422
    batch = bind(admin, batch, first["id"], target)
    # An older editor omitting new fields must not silently change update into create.
    batch = assign(admin, batch, first["id"], target["topic_id"])
    assert (
        next(c for c in batch["candidates"] if c["id"] == first["id"])["target_article_id"]
        == target["id"]
    )
    duplicate = admin.put(
        A + f"/imports/{batch['id']}/candidates/{second['id']}",
        headers=key(),
        json={
            "revision": batch["revision"],
            "topic_id": target["topic_id"],
            "payload": second["payload"],
            "target_article_id": target["id"],
            "target_revision": target["revision"],
        },
    )
    assert (
        duplicate.status_code == 409
        and duplicate.json()["error"]["code"] == "listening_target_duplicate"
    )


def test_explicit_identical_update_is_reported_as_skip_without_revision_or_new_article(admin):
    target = article(admin)
    batch = staged(admin)
    cid = batch["candidates"][0]["id"]
    batch = bind(admin, batch, cid, target, payload=target["payload"])
    preview = confirm(admin, batch)
    assert preview["changes"][0]["before"] == preview["changes"][0]["after"]
    saved = post(
        admin, A + f"/imports/{batch['id']}/save", {"preview_token": preview["preview_token"]}
    )
    assert (
        saved["items"][0]["status"] == "skipped" and saved["items"][0]["article_id"] == target["id"]
    )
    assert admin.get(A + f"/articles/{target['id']}").json()["revision"] == target["revision"]
    assert admin.get(A + "/articles").json()["total"] == 1
    assert admin.get(A + "/articles", params={"batch_id": batch["id"]}).json()["total"] == 1


def test_original_import_batch_membership_survives_later_batch_update(admin):
    t = topic(admin)
    original = staged(admin, "原批次资料")
    cid = original["candidates"][0]["id"]
    original = assign(admin, original, cid, t["id"])
    original_save = post(
        admin,
        A + f"/imports/{original['id']}/save",
        {"preview_token": confirm(admin, original)["preview_token"]},
    )
    target = admin.get(A + "/articles/" + original_save["items"][0]["article_id"]).json()
    batch = staged(admin, "新批次更新资料")
    batch = bind(admin, batch, batch["candidates"][0]["id"], target)
    post(
        admin,
        A + f"/imports/{batch['id']}/save",
        {"preview_token": confirm(admin, batch)["preview_token"]},
    )
    actual = admin.get(A + f"/articles/{target['id']}").json()
    assert actual["batch_id"] == original["id"]
    for batch_id in [batch["id"], original["id"]]:
        listed = admin.get(A + "/articles", params={"batch_id": batch_id}).json()
        assert [r["id"] for r in listed["items"]] == [target["id"]]


def test_target_media_preview_and_timeline_recheck_bound_revision_and_word_positions(admin):
    target = article(admin)
    batch = staged(admin)
    cid = batch["candidates"][0]["id"]
    payload = {**batch["candidates"][0]["payload"], "audio_id": target["payload"]["audio_id"]}
    batch = bind(admin, batch, cid, target, payload=payload)
    invalid_words = {
        **payload,
        "word_meanings": [{"start": 0, "end": 5, "word": "Birds", "chinese": "鸟"}],
    }
    response = admin.put(
        A + f"/imports/{batch['id']}/candidates/{cid}",
        headers=key(),
        json={
            "revision": batch["revision"],
            "topic_id": target["topic_id"],
            "payload": invalid_words,
            "target_article_id": target["id"],
            "target_revision": target["revision"],
        },
    )
    assert (
        response.status_code == 422
        and response.json()["error"]["code"] == "listening_word_reference_invalid"
    )
    admin.put(
        A + f"/articles/{target['id']}",
        headers=key(),
        json={
            "revision": target["revision"],
            "topic_id": target["topic_id"],
            "payload": target["payload"],
        },
    )
    assert admin.get(A + f"/imports/{batch['id']}/media/{payload['audio_id']}").status_code == 409
    assert admin.get(A + f"/imports/{batch['id']}/candidates/{cid}/timeline").status_code == 409
    assert admin.get(A + f"/articles/{target['id']}").json()["payload"] == target["payload"]


def test_idempotency_distinguishes_omitted_target_binding_from_explicit_clear(admin):
    target = article(admin)
    batch = staged(admin)
    cid = batch["candidates"][0]["id"]
    batch = bind(admin, batch, cid, target)
    candidate = batch["candidates"][0]
    headers = key()
    body = {
        "revision": batch["revision"],
        "topic_id": target["topic_id"],
        "payload": candidate["payload"],
    }
    path = A + f"/imports/{batch['id']}/candidates/{cid}"
    assert admin.put(path, headers=headers, json=body).status_code == 200
    changed_request = {**body, "target_article_id": None, "target_revision": None}
    response = admin.put(path, headers=headers, json=changed_request)
    assert response.status_code == 409 and response.json()["error"]["code"] == "operation_conflict"


def test_same_media_bytes_with_new_ids_skip_against_current_target_not_original_source(admin, mini):
    t = topic(admin)
    original = staged(admin, "原资料")
    cid = original["candidates"][0]["id"]
    original = assign(admin, original, cid, t["id"])
    created = post(
        admin,
        A + f"/imports/{original['id']}/save",
        {"preview_token": confirm(admin, original)["preview_token"]},
    )
    target = admin.get(A + "/articles/" + created["items"][0]["article_id"]).json()
    image = admin.post(
        A + f"/articles/{target['id']}/media?kind=image",
        headers=key(),
        files={"file": ("original.png", picture(), "image/png")},
    ).json()
    target = admin.put(
        A + f"/articles/{target['id']}",
        headers=key(),
        json={
            "revision": target["revision"],
            "topic_id": target["topic_id"],
            "payload": {**target["payload"], "image_id": image["id"]},
        },
    ).json()
    target = publish(admin, target)
    policy(admin, 1)
    post(mini, M + f"/articles/{target['id']}/complete", {"version_id": target["version_id"]})
    assert (
        mini.put(
            M + f"/articles/{target['id']}/favorite",
            headers=key(),
            json={"version_id": target["version_id"]},
        ).status_code
        == 200
    )
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("item/content.docx", document("最初有差异的候选"))
        archive.writestr("item/complete.wav", recording())
        archive.writestr("item/image.png", picture())
    batch = upload(admin, post(admin, A + "/imports", {"mode": "zip"}), stream.getvalue())
    candidate = batch["candidates"][0]
    assert candidate["payload"]["audio_id"] != target["payload"]["audio_id"]
    assert candidate["payload"]["image_id"] != target["payload"]["image_id"]
    payload = {
        **target["payload"],
        "audio_id": candidate["payload"]["audio_id"],
        "image_id": candidate["payload"]["image_id"],
    }
    batch = bind(admin, batch, candidate["id"], target, payload=payload)
    saved = post(
        admin,
        A + f"/imports/{batch['id']}/save",
        {"preview_token": confirm(admin, batch)["preview_token"]},
    )
    assert saved["items"][0]["status"] == "skipped"
    actual = admin.get(A + f"/articles/{target['id']}").json()
    assert actual["revision"] == target["revision"] and actual["payload"] == target["payload"]
    assert actual["version_id"] == target["version_id"] and actual["batch_id"] == original["id"]
    live = mini.get(M + f"/articles/{target['id']}").json()
    assert (
        live["payload"] == target["payload"]
        and live["state"]["favorite"]
        and live["state"]["completed"]
    )
    assert admin.get(A + "/articles").json()["total"] == 1
    # Skipped copies are batch references, not grants to unused replacement media.
    assert (
        admin.get(
            A + f"/articles/{target['id']}/media/{candidate['payload']['audio_id']}"
        ).status_code
        == 404
    )


@pytest.mark.mysql
@pytest.mark.skipif(not os.getenv("JUYA_TEST_DATABASE_URL"), reason="Dedicated MySQL required")
def test_two_batches_confirming_same_revision_have_one_update_winner(admin, system):
    target = article(admin)
    batches = [staged(admin, title) for title in ["甲更新", "乙更新"]]
    previews = []
    for batch in batches:
        batch = bind(admin, batch, batch["candidates"][0]["id"], target)
        previews.append((batch["id"], confirm(admin, batch)["preview_token"]))

    def save(value):
        bid, token = value
        return admin.post(A + f"/imports/{bid}/save", headers=key(), json={"preview_token": token})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(save, previews))
    assert [r.status_code for r in responses] == [200, 200]
    assert sorted(r.json()["items"][0]["status"] for r in responses) == ["failed", "success"]
    assert admin.get(A + f"/articles/{target['id']}").json()["revision"] == target["revision"] + 1
