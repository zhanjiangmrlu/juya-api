"""Only this entrypoint is deployed on admin-api.juyayingyu.com."""

from .admin_action_api import routes as action_routes
from .application import application
from .auth import admin_routes
from .config import Settings
from .content_api import admin_routes as content_routes
from .feedback_api import routes as feedback_routes
from .feedback_safety import FeedbackSafetyGateway
from .import_api import routes as import_routes
from .list_thumbnails import ListThumbnails
from .media_api import admin_routes as media_routes
from .operation_api import routes as operation_routes
from .pronunciation_api import routes as pronunciation_routes
from .publication_api import routes as publication_routes
from .users_api import routes as users_routes


def create_app(
    settings: Settings | None = None, *, sessions=None, clock=None, feedback_safety=None
):
    """Construct the administration-only API without learner routes."""
    settings = settings or Settings()
    app = application("admin", settings, sessions, clock)
    app.state.feedback_safety = (
        feedback_safety if feedback_safety is not None else FeedbackSafetyGateway(settings)
    )
    app.state.list_thumbnails = ListThumbnails()
    app.include_router(admin_routes())
    app.include_router(content_routes())
    app.include_router(action_routes())
    app.include_router(media_routes())
    app.include_router(users_routes())
    app.include_router(publication_routes())
    app.include_router(import_routes())
    app.include_router(operation_routes("admin"))
    app.include_router(pronunciation_routes("admin"))
    app.include_router(feedback_routes("admin"))
    return app
