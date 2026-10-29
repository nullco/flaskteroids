from flask import has_request_context
from werkzeug.wrappers import Response

from flaskteroids.application import Application


class RecordingMiddleware:
    def __init__(self, app, events, *, label=None):
        self.app = app
        self.events = events
        self.label = label or type(self).__name__
        events.append(("build", self.label))

    def __call__(self, environ, start_response):
        self.events.append(("before", self.label))
        try:
            return self.app(environ, start_response)
        finally:
            self.events.append(("after", self.label))


class First(RecordingMiddleware):
    pass


class Second(RecordingMiddleware):
    pass


class Third(RecordingMiddleware):
    pass


class EarlyResponse:
    def __init__(self, app, *, message="maintenance"):
        self.app = app
        self.message = message

    def __call__(self, environ, start_response):
        assert not has_request_context()
        return Response(self.message, status=503)(environ, start_response)


class ConfiguredApplication(Application):
    def configure(self, config):
        config.paths.routes = "tests.middleware.support"
        for name in ("models", "controllers", "jobs", "mailers", "helpers"):
            setattr(config.paths, name, f"missing.{name}")
        config.secret_key_base = "middleware-test"
        config.controller.allow_forgery_protection = False
        config["MIDDLEWARE_EVENTS"] = []
        config.middleware.use(First, config["MIDDLEWARE_EVENTS"])

    def _configure_database(self):
        self.database_url = "sqlite:///:memory:"


def register(route):
    route.get("/up/", to="flaskteroids/health#show")
