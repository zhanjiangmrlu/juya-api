import io
import uuid
import wave

from PIL import Image


def key():
    return {"Idempotency-Key": uuid.uuid4().hex}


def picture():
    output = io.BytesIO()
    Image.new("RGB", (120, 80), "#c8e2b5").save(output, format="PNG")
    return output.getvalue()


def recording():
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 16000)
    return output.getvalue()


def content(admin):
    image = admin.post(
        "/api/admin/v1/media?kind=image",
        headers=key(),
        files={"file": ("scene.png", picture(), "image/png")},
    )
    assert image.status_code == 201, image.text
    audio = admin.post(
        "/api/admin/v1/media?kind=audio",
        headers=key(),
        files={"file": ("dialogue.wav", recording(), "audio/wav")},
    )
    assert audio.status_code == 201, audio.text
    process_jobs(admin)
    return {
        "name": "在咖啡店点单",
        "title_en": "Ordering Coffee",
        "image_id": image.json()["id"],
        "audio_id": audio.json()["id"],
        "dialogue": [
            {
                "id": "line-1",
                "speaker": "A",
                "english": "I'd like a coffee, please.",
                "chinese": "我想要一杯咖啡，谢谢。",
            }
        ],
        "vocabulary": [{"id": "word-1", "english": "coffee", "meaning": "咖啡"}],
        "chunks": [],
    }


def draft(admin, payload=None):
    response = admin.post(
        "/api/admin/v1/cards", json={"content": payload or content(admin)}, headers=key()
    )
    assert response.status_code == 201, response.text
    return response.json()


def publish(admin, card):
    preview = admin.post(
        f"/api/admin/v1/cards/{card['id']}/preview",
        json={"revision": card["draft_revision"]},
        headers=key(),
    )
    assert preview.status_code == 200, preview.text
    response = admin.post(
        f"/api/admin/v1/cards/{card['id']}/publish",
        headers=key(),
        json={"revision": card["draft_revision"], "preview_id": preview.json()["preview_id"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def process_jobs(client):
    from sqlalchemy import select

    from juya_api.job_models import Job
    from juya_api.worker import run_job

    app = client.app
    for _ in range(20):
        with app.state.sessions() as db:
            pending = db.scalars(select(Job.id).where(Job.state == "queued")).all()
        if not pending:
            return
        for job_id in pending:
            run_job(app.state.settings, app.state.sessions, job_id, clock=app.state.clock)
    raise AssertionError("Worker did not settle accepted tasks")
