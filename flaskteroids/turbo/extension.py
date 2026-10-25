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


def init_turbo(app):
    if app.extensions.get("flaskteroids.turbo"):
        return
    app.extensions["flaskteroids.turbo"] = True
    app.jinja_env.loader = ChoiceLoader(
        [app.jinja_env.loader, PackageLoader("flaskteroids.turbo", "templates")]
    )
    app.context_processor(template_context)

    @app.after_request
    def vary_representation(response):
        rendered = getattr(g, "_flaskteroids_turbo_rendered", False)
        controller = getattr(g, "controller", None)
        if not rendered and controller is None:
            return response
        if response.mimetype not in {"text/html", "application/json", STREAM_MIMETYPE}:
            return response
        response.vary.update(("Accept", "Turbo-Frame"))
        etag, weak = response.get_etag()
        if etag is not None:
            variant = "frame" if turbo_frame_request() else "page"
            identity = f"{etag}\0{response.mimetype}\0{variant}".encode()
            response.set_etag(sha256(identity).hexdigest(), weak=weak)
        return response
