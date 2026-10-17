"""Only this entrypoint is deployed on admin-api.juyayingyu.com."""

from .application import application
from .auth import admin_routes
from .config import Settings
from .content_api import admin_routes as content_routes
from .media_api import admin_routes as media_routes
from .operation_api import routes as operation_routes
from .pronunciation_api import routes as pronunciation_routes
from .publication_api import routes as publication_routes
from .users_api import routes as users_routes


def create_app(settings: Settings | None = None, *, sessions=None, clock=None):
    """Construct the administration-only API without learner routes."""
    app = application("admin", settings or Settings(), sessions, clock)
    app.include_router(admin_routes())
    app.include_router(content_routes())
    app.include_router(media_routes())
    app.include_router(users_routes())
    app.include_router(publication_routes())
    app.include_router(operation_routes("admin"))
    app.include_router(pronunciation_routes("admin"))
    return app
