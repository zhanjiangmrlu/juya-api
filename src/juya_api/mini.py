"""Only this entrypoint is deployed on api.juyayingyu.com."""

from .application import application
from .auth import WechatGateway, mini_routes
from .config import Settings
from .content_api import mini_routes as content_routes
from .learning_api import routes as learning_routes
from .list_thumbnails import ListThumbnails
from .media_api import mini_routes as media_routes
from .operation_api import routes as operation_routes
from .profile_api import routes as profile_routes
from .pronunciation_api import routes as pronunciation_routes


def create_app(settings: Settings | None = None, *, sessions=None, clock=None, wechat=None):
    """Construct the learner-only API with a replaceable external WeChat gateway."""
    settings = settings or Settings()
    app = application("mini", settings, sessions, clock)
    app.state.wechat = wechat or WechatGateway(settings)
    app.state.list_thumbnails = ListThumbnails()
    app.include_router(mini_routes())
    app.include_router(content_routes())
    app.include_router(media_routes())
    app.include_router(learning_routes())
    app.include_router(profile_routes())
    app.include_router(operation_routes("mini"))
    app.include_router(pronunciation_routes("mini"))
    return app
