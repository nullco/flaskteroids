from functools import wraps

from flask import (
    current_app,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
)
from werkzeug.wrappers import Response as BaseResponse

from flaskteroids._view_helpers import controller_scope
from flaskteroids._view_helpers import helper as helper
from flaskteroids._view_helpers import helper_method as helper_method
from flaskteroids.actions import (
    ActionParameters,
    decorate_action,
    get_actions,
    mark_action_wrapper,
    original_action,
    register_actions,
)
from flaskteroids.declarations import actions_for
from flaskteroids.exceptions import DoubleRenderError, ProgrammerError
from flaskteroids.flash import flash
from flaskteroids.inflector import inflector
from flaskteroids.rules import bind_rules

_UNSET = object()


def init(cls):
    definition = actions_for(cls)
    if definition.prepared:
        return cls
    register_actions(cls, ActionController)
    bind_rules(cls)
    _decorate_actions(cls)
    definition.prepared = True
    return cls


def _decorate_actions(cls):
    for name in get_actions(cls):
        action = original_action(cls, name)
        setattr(cls, name, _decorate_action(cls, action))


def _decorate_action(cls, action):
    original = action

    @wraps(action)
    def invoke(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        if not self.performed and result is not None:
            self._prepare_response(result)
        if not self.performed and self._action_depth == 1:
            self.render()
        return self.response if self.performed else None

    action = decorate_action(
        cls, invoke, performed=lambda controller: controller.performed
    )

    @wraps(action)
    def wrapper(self, *args, **kwargs):
        depth = getattr(self, "_action_depth", None)
        outermost = not depth
        if outermost:
            if depth is not None or self.performed:
                self._response = None
            self._performed = False
            self._action_name = action.__name__
            self._action_depth = 0
        self._action_depth += 1
        try:
            result = action(self, *args, **kwargs)
            if not self.performed and result is not None:
                self._prepare_response(result)
            if not self.performed and outermost:
                self.render()
            return self.response if self.performed else None
        finally:
            self._action_depth -= 1

    return mark_action_wrapper(wrapper, original)


def _serialize_json(value):
    serializer = getattr(value, "__json__", None)
    if callable(serializer):
        return _serialize_json(serializer())
    if isinstance(value, dict):
        return {key: _serialize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_json(item) for item in value]
    return value


class ActionController:
    __slots__ = (
        "_params",
        "_response",
        "_performed",
        "_action_name",
        "_action_depth",
        "__dict__",
        "__weakref__",
    )

    def __init__(self, *args, **kwargs) -> None:
        g.controller = self

    @property
    def params(self) -> ActionParameters:
        if not hasattr(self, "_params"):
            self._params = ActionParameters()
        return self._params

    @property
    def response(self):
        if getattr(self, "_response", None) is None:
            self._response = current_app.response_class()
            self._response.headers.pop("Content-Type", None)
            self._response.headers.pop("Content-Length", None)
        return self._response

    @property
    def performed(self) -> bool:
        return getattr(self, "_performed", False)

    def _ensure_response_available(self):
        if self.performed:
            raise DoubleRenderError("This controller has already prepared a response.")

    def _prepare_response(self, response):
        self._ensure_response_available()
        response = (
            make_response(response)
            if isinstance(response, (BaseResponse, tuple))
            else make_response(response, self.response.status_code)
        )
        supplied = {name.lower() for name in response.headers.keys()}
        for name, value in self.response.headers:
            if name.lower() not in supplied:
                response.headers.add(name, value)
        self._response = response
        self._performed = True
        return response

    def redirect_to(self, target, *, status=302, notice=None, alert=None):
        self._ensure_response_available()
        if target is None:
            raise ProgrammerError("redirect_to() requires a destination.")
        response = redirect(target, code=status or 302)
        response.set_data("")
        response = self._prepare_response(response)
        if notice is not None:
            flash["notice"] = notice
        if alert is not None:
            flash["alert"] = alert
        return response

    def head(self, status=_UNSET, headers=None):
        self._ensure_response_available()
        status = self.response.status_code if status is _UNSET else status
        response = make_response("", status)
        if headers:
            response.headers.update(headers)
        response = self._prepare_response(response)
        if 100 <= response.status_code < 200 or response.status_code in (204, 205, 304):
            response.headers.pop("Content-Type", None)
            response.headers.pop("Content-Length", None)
        return response

    def respond_to(self, *, html=None, json=None):
        self._ensure_response_available()
        handlers = {
            mime: handler
            for mime, handler in (("text/html", html), ("application/json", json))
            if handler is not None
        }
        if any(not callable(handler) for handler in handlers.values()):
            raise ProgrammerError("respond_to() handlers must be callable.")
        if request.path.rstrip("/").endswith(".json"):
            mime = "application/json"
        elif request.headers.get("Accept"):
            mime = request.accept_mimetypes.best_match(handlers)
        else:
            mime = "text/html"
        handler = handlers.get(mime)
        if handler is None:
            self._prepare_response(make_response("406 Not Acceptable", 406))
        else:
            result = handler()
            if not self.performed and result is not None:
                self._prepare_response(result)
            if not self.performed and mime == "application/json":
                raise ProgrammerError(
                    "A JSON handler must render or return a response."
                )
        return self.response if self.performed else None

    def render(self, action=None, *, status=_UNSET, json=_UNSET):
        self._ensure_response_available()
        status = self.response.status_code if status is _UNSET else status
        if json is not _UNSET:
            if action is not None:
                raise ProgrammerError("Choose either a template or JSON to render.")
            response = make_response(jsonify(_serialize_json(json)), status)
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
            with controller_scope(self):
                view = render_template(
                    f"{template}.html", **{**vars(self), "params": self.params}
                )
            response = make_response(view, status)
        return self._prepare_response(response)
