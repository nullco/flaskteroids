from flask import (
    current_app,
    has_request_context,
    make_response,
    render_template,
    request,
)
from jinja2 import TemplateNotFound
from markupsafe import Markup

from flaskteroids._controllers.api import APIController as APIController
from flaskteroids._controllers.base import _UNSET, ControllerBase, prepare_controller
from flaskteroids._controllers.parameters import wrap_parameters as wrap_parameters
from flaskteroids._view_helpers import controller_scope
from flaskteroids._view_helpers import helper as helper
from flaskteroids._view_helpers import helper_method as helper_method
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.flash import flash
from flaskteroids.inflector import inflector
from flaskteroids.turbo import TurboStreamBuilder
from flaskteroids.turbo.extension import STREAM_MIMETYPE as _STREAM_MIME
from flaskteroids.turbo.extension import (
    inherit_response_etag,
    turbo_frame_request,
    turbo_frame_request_id,
)
from flaskteroids.turbo.rendering import render as render_view


def _negotiate_mime(offered):
    if not has_request_context():
        return "text/html"
    path = request.path.rstrip("/")
    if path.endswith(".json"):
        return "application/json"
    if path.endswith(".turbo_stream"):
        return _STREAM_MIME
    if not request.headers.get("Accept"):
        return "text/html"
    offered = list(offered)
    accepted = [mime for mime, _quality in request.accept_mimetypes]
    if _STREAM_MIME in accepted:
        offered.sort(
            key=lambda mime: accepted.index(mime) if mime in accepted else len(accepted)
        )
    return request.accept_mimetypes.best_match(offered)


def init(cls):
    return cls._flaskteroids_prepare()


class ActionController(ControllerBase):
    layout = "layouts/application.html"
    frame_layout = "layouts/turbo/frame.html"

    @classmethod
    def _flaskteroids_prepare(cls):
        return prepare_controller(cls, ActionController)

    @classmethod
    def _prepare_views(cls, helpers):
        helpers.validate_controller(cls)

    def _default_render(self):
        return self.render()

    def _inherit_response_metadata(self, response):
        inherit_response_etag(self.response, response)

    def _response_variant(self):
        return "frame" if self.turbo_frame_request else "page"

    @property
    def turbo_frame_request_id(self):
        return turbo_frame_request_id()

    @property
    def turbo_frame_request(self) -> bool:
        return turbo_frame_request()

    @property
    def turbo_stream(self):
        return TurboStreamBuilder(renderer=self._render_stream_partial)

    def _render_stream_partial(self, *args, **kwargs):
        with controller_scope(self):
            return render_view(*args, **kwargs)

    def redirect_to(self, target, *, status=302, notice=None, alert=None):
        response = super().redirect_to(target, status=status)
        if notice is not None:
            flash["notice"] = notice
        if alert is not None:
            flash["alert"] = alert
        return response

    def respond_to(self, *, html=None, json=None, turbo_stream=None):
        self._ensure_response_available()
        handlers = {
            mime: handler
            for mime, handler in (
                ("text/html", html),
                ("application/json", json),
                (_STREAM_MIME, turbo_stream),
            )
            if handler is not None
        }
        if any(not callable(handler) for handler in handlers.values()):
            raise ProgrammerError("respond_to() handlers must be callable.")
        mime = _negotiate_mime(handlers)
        self._response_mime = mime
        handler = handlers.get(mime)
        if handler is None:
            self._prepare_response(make_response("406 Not Acceptable", 406))
        else:
            result = handler()
            if not self.performed and result is not None:
                if mime == _STREAM_MIME and isinstance(result, str):
                    result = make_response(result, self.response.status_code)
                    result.mimetype = _STREAM_MIME
                self._prepare_response(result)
            if not self.performed and mime == "application/json":
                raise ProgrammerError(
                    "A JSON handler must render or return a response."
                )
        return self.response if self.performed else None

    def render(
        self,
        action=None,
        *,
        status=_UNSET,
        json=_UNSET,
        turbo_stream=_UNSET,
        location=None,
    ):
        self._ensure_response_available()
        if (
            sum((action is not None, json is not _UNSET, turbo_stream is not _UNSET))
            > 1
        ):
            raise ProgrammerError("Choose a template, JSON, or Turbo Stream to render.")
        status = self.response.status_code if status is _UNSET else status
        if json is not _UNSET:
            return super().render(json=json, status=status, location=location)
        if location is not None:
            raise ProgrammerError("location= requires JSON rendering.")
        if turbo_stream is not _UNSET:
            operations = (
                turbo_stream
                if isinstance(turbo_stream, (list, tuple))
                else (turbo_stream,)
            )
            if any(not isinstance(operation, str) for operation in operations):
                raise ProgrammerError(
                    "Turbo Stream operations must be strings or Markup."
                )
            response = make_response(Markup("").join(operations), status)
            response.mimetype = _STREAM_MIME
        else:
            action = (
                action if action is not None else getattr(self, "_action_name", None)
            )
            if not action:
                raise ProgrammerError(
                    "Specify a template when rendering outside an action."
                )
            cname = inflector.underscore(type(self).__name__.removesuffix("Controller"))
            template = action if "/" in action else f"{cname}/{action}"
            mime = getattr(self, "_response_mime", None) or _negotiate_mime(
                ("text/html", _STREAM_MIME)
            )
            template_name = f"{template}.html"
            if mime == _STREAM_MIME:
                stream_template = f"{template}.turbo_stream.html"
                try:
                    current_app.jinja_env.get_template(stream_template)
                except TemplateNotFound:
                    if (
                        request.path.rstrip("/").endswith(".turbo_stream")
                        or request.accept_mimetypes["text/html"] <= 0
                    ):
                        raise
                    mime = "text/html"
                else:
                    template_name = stream_template
            assigns = {
                key: value for key, value in vars(self).items() if key != "layout"
            }
            with controller_scope(self):
                view = render_template(
                    template_name, **{**assigns, "params": self.params}
                )
            response = make_response(view, status)
            if mime == _STREAM_MIME:
                response.mimetype = _STREAM_MIME
        return self._prepare_response(response)
