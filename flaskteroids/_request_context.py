"""Adopt middleware-parsed requests and preserve framework routing errors."""

import sys

from flask.ctx import RequestContext
from werkzeug.exceptions import MethodNotAllowed, NotFound

from flaskteroids._method_override import (
    APP_CONTEXT,
    PREPARED_REQUEST,
    TEARDOWN_ERROR,
    TRANSPORT_ERROR,
)

_UNSET = object()


class RoutingRequestContext(RequestContext):
    def __init__(self, app, environ, request=None, session=None):
        prepared = environ.get(PREPARED_REQUEST)
        if request is None:
            request = prepared
        super().__init__(app, environ, request=request, session=session)
        if request is not None and request is prepared:
            environ.pop(PREPARED_REQUEST, None)

    def pop(self, exc=_UNSET):
        if exc is _UNSET:
            exc = sys.exception()
        if self.request.environ.get(APP_CONTEXT):
            self.request.environ[TEARDOWN_ERROR] = exc
        return super().pop(exc)

    def match_request(self):
        error = self.request.environ.get(TRANSPORT_ERROR)
        if error is not None:
            self.request.environ["flaskteroids.routing_error"] = True
            self.request.routing_exception = error
            return
        super().match_request()
        error = self.request.routing_exception
        routes = self.app.extensions.get("flaskteroids.routes")
        if (
            routes is not None
            and isinstance(error, MethodNotAllowed)
            and routes.owns_method_miss(self.url_adapter, error)
        ):
            self.request.environ["flaskteroids.routing_error"] = True
            self.request.routing_exception = NotFound()
