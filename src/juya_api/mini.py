"""Only this entrypoint is deployed on api.juyayingyu.com."""

from .application import application
from .auth import WechatGateway, mini_routes
from .config import Settings


def create_app(settings: Settings | None = None, *, sessions=None, clock=None, wechat=None):
    """Construct the learner-only API with a replaceable external WeChat gateway."""
    settings = settings or Settings()
    app = application("mini", settings, sessions, clock)
    app.state.wechat = wechat or WechatGateway(settings)
    app.include_router(mini_routes())
    return app
