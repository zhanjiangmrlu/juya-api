"""Only this entrypoint is deployed on admin-api.juyayingyu.com."""

from .application import application
from .auth import admin_routes
from .config import Settings


def create_app(settings: Settings | None = None, *, sessions=None, clock=None):
    """Construct the administration-only API without learner routes."""
    app = application("admin", settings or Settings(), sessions, clock)
    app.include_router(admin_routes())
    return app
