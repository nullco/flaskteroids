"""Request-scoped layout selection and representation-aware response metadata."""

from hashlib import sha256

from flask import g, has_request_context, request
from jinja2 import ChoiceLoader, PackageLoader

from flaskteroids._view_helpers import render_scope

FRAME_LAYOUT = "layouts/turbo/frame.html"
APPLICATION_LAYOUT = "layouts/application.html"
STREAM_MIMETYPE = "text/vnd.turbo-stream.html"


def turbo_frame_request_id():
    value = request.headers.get("Turbo-Frame") if has_request_context() else None
    return value if value and value.strip() else None


def turbo_frame_request():
    return bool((turbo_frame_request_id() or "").strip())


def template_context():
    scope = render_scope.get()
    if scope is not None:
        kind, owner = scope
        if kind != "controller":
            return {}
    else:
        owner = getattr(g, "controller", None) if has_request_context() else None
    if has_request_context():
        g._flaskteroids_turbo_rendered = True
    frame = turbo_frame_request()
    return {
        "layout": getattr(owner, "frame_layout", FRAME_LAYOUT)
        if frame
        else getattr(owner, "layout", APPLICATION_LAYOUT),
        "turbo_frame_request": turbo_frame_request,
        "turbo_frame_request_id": turbo_frame_request_id,
    }


def _response_variant():
    controller = getattr(g, "controller", None)
    if controller is not None:
        return controller._response_variant()
    if getattr(g, "_flaskteroids_turbo_rendered", False):
        return "frame" if turbo_frame_request() else "page"
    return None


class _FrameETagResponse:
    def set_etag(self, etag, weak=False):
        super().set_etag(etag, weak=weak)
        self._turbo_etag_source = (etag, weak)
        self._turbo_etag_header = self.headers.get("ETag")
        self._finalize_turbo_etag()

    def _managed_turbo_etag(self):
        source = getattr(self, "_turbo_etag_source", None)
        if source is not None and self.headers.get("ETag") != self._turbo_etag_header:
            self._turbo_etag_source = None
            return None
        return source

    def _finalize_turbo_etag(self):
        source = self._managed_turbo_etag()
        if source is None:
            return
        etag, weak = source
        variant = _response_variant() if has_request_context() else None
        if self.mimetype and variant is not None:
            identity = f"{etag}\0{self.mimetype}\0{variant}".encode()
            etag = sha256(identity).hexdigest()
        super().set_etag(etag, weak=weak)
        self._turbo_etag_header = self.headers.get("ETag")

    def make_conditional(
        self, request_or_environ, accept_ranges=False, complete_length=None
    ):
        self._finalize_turbo_etag()
        return super().make_conditional(
            request_or_environ,
            accept_ranges=accept_ranges,
            complete_length=complete_length,
        )


def inherit_response_etag(source, target):
    if isinstance(source, _FrameETagResponse) and "ETag" not in target.headers:
        etag = source._managed_turbo_etag()
        if etag is not None:
            target.set_etag(etag[0], weak=etag[1])


def init_turbo(app):
    if app.extensions.get("flaskteroids.turbo"):
        return
    app.extensions["flaskteroids.turbo"] = True
    app.response_class = type(
        "TurboResponse", (_FrameETagResponse, app.response_class), {}
    )
    app.jinja_env.loader = ChoiceLoader(
        [app.jinja_env.loader, PackageLoader("flaskteroids.turbo", "templates")]
    )

    @app.after_request
    def vary_representation(response):
        if _response_variant() is None:
            return response
        if isinstance(response, _FrameETagResponse):
            response._finalize_turbo_etag()
        if response.mimetype in {"text/html", "application/json", STREAM_MIMETYPE}:
            response.vary.update(("Accept", "Turbo-Frame"))
        return response
