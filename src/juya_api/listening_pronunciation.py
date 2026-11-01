"""Controlled listening vocabulary speech reuses the global word synthesis cache."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from .dependencies import administrator, database, learner, operation_key
from .errors import DomainError
from .listening_models import ListeningCandidate
from .listening_service import published, require_article
from .pronunciation import request as request_speech
from .pronunciation import status, word_reference
from .pronunciation_api import SpeechReference, SpeechState, with_grant
from .transactions import operate


def reference(
    db,
    settings,
    role,
    actor_id,
    article_id,
    word_id,
    version_id=None,
    revision=None,
    *,
    context=None,
    now=None,
):
    """Resolve saved article or owned staging words; clients never supply synthesis text."""
    if (version_id is None) == (revision is None) or (role == "mini" and not version_id):
        raise DomainError(422, "word_reference_required", "请明确文章版本或核对资料版本")
    if context and (version_id is not None or revision is None):
        raise DomainError(422, "word_reference_required", "请明确当前导入批次版本")
    if context:
        from .listening_imports import owned

        batch = owned(db, context["batch_id"], actor_id, revision)
        candidate = db.get(ListeningCandidate, context["candidate_id"])
        if (
            not candidate
            or candidate.batch_id != batch.id
            or candidate.removed
            or candidate.state == "unreadable"
        ):
            raise DomainError(404, "word_missing", "未找到核对词汇")
        payload = candidate.payload
    elif version_id:
        if role == "mini":
            _, version = published(db, actor_id, article_id, now, version_id)
        else:
            from .listening_service import admin_publication

            _, version = admin_publication(db, article_id)
            if version.id != version_id:
                raise DomainError(409, "listening_version_changed", "发布版本已变化")
        payload = version.payload
    elif role == "admin" and revision is not None:
        payload = require_article(db, article_id, revision).payload
    else:
        raise DomainError(422, "word_reference_required", "请重新打开词汇后试听")
    return word_reference(settings, {"vocabulary": payload.get("vocabulary", [])}, word_id)


def routes(role):
    """Offer version-bound single-word speech for each isolated API role."""
    router = APIRouter(prefix=f"/api/{role}/v1/listening", tags=["listening word pronunciation"])
    authorize = administrator if role == "admin" else learner

    def result(
        db, request, actor, article_id, word_id, ref, *, create=False, key=None, context=None
    ):
        """Refresh references inside the receipt transaction before starting synthesis."""
        args = (
            db,
            request.app.state.settings,
            role,
            actor.id,
            article_id,
            word_id,
            ref.version_id,
            ref.revision,
        )
        word, reading, config, cache_key = reference(
            *args, context=context, now=request.app.state.clock()
        )

        def execute():
            """Recheck publication and authorization after operation locks are acquired."""
            word, reading, config, cache_key = reference(
                *args, context=context, now=request.app.state.clock()
            )
            return request_speech(
                db,
                request.app.state.settings,
                actor,
                role,
                word,
                reading,
                config,
                cache_key,
                request.app.state.clock(),
            )

        value = (
            operate(
                db,
                actor,
                role,
                key,
                "listening.word:" + (article_id or context["candidate_id"]) + ":" + word_id,
                ref.model_dump(),
                request.app.state.clock(),
                execute,
            )
            if create
            else status(db, cache_key)
        )
        return with_grant(
            value,
            request,
            role,
            actor.id,
            article_id,
            word_id,
            ref,
            cache_key,
            listening_context=context or {"article_id": article_id},
        )

    @router.get("/articles/{article_id}/words/{word_id}/pronunciation", response_model=SpeechState)
    def read(
        article_id: str,
        word_id: str,
        request: Request,
        version_id: str | None = Query(None, max_length=36),
        revision: int | None = Query(None, ge=1),
        actor=Depends(authorize),
        db: Session = Depends(database, scope="function"),
    ):
        """Read persistent speech state without starting a cloud task."""
        return result(
            db,
            request,
            actor,
            article_id,
            word_id,
            SpeechReference(version_id=version_id, revision=revision),
        )

    @router.post("/articles/{article_id}/words/{word_id}/pronunciation", response_model=SpeechState)
    def generate(
        article_id: str,
        word_id: str,
        body: SpeechReference,
        request: Request,
        actor=Depends(authorize),
        key=Depends(operation_key),
        db: Session = Depends(database, scope="function"),
    ):
        """Generate one server-resolved vocabulary word with persistent idempotency."""
        return result(db, request, actor, article_id, word_id, body, create=True, key=key)

    if role == "admin":

        @router.get(
            "/imports/{batch_id}/candidates/{candidate_id}/words/{word_id}/pronunciation",
            response_model=SpeechState,
        )
        def read_candidate(
            batch_id: str,
            candidate_id: str,
            word_id: str,
            request: Request,
            revision: int = Query(..., ge=1),
            actor=Depends(authorize),
            db: Session = Depends(database, scope="function"),
        ):
            """Preview owned staging words without recording any learner facts."""
            return result(
                db,
                request,
                actor,
                None,
                word_id,
                SpeechReference(revision=revision),
                context={"batch_id": batch_id, "candidate_id": candidate_id},
            )

        @router.post(
            "/imports/{batch_id}/candidates/{candidate_id}/words/{word_id}/pronunciation",
            response_model=SpeechState,
        )
        def generate_candidate(
            batch_id: str,
            candidate_id: str,
            word_id: str,
            body: SpeechReference,
            request: Request,
            actor=Depends(authorize),
            key=Depends(operation_key),
            db: Session = Depends(database, scope="function"),
        ):
            """Start controlled staging word synthesis against the current batch revision."""
            return result(
                db,
                request,
                actor,
                None,
                word_id,
                body,
                create=True,
                key=key,
                context={"batch_id": batch_id, "candidate_id": candidate_id},
            )

    return router
