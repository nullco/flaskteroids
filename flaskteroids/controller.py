from functools import wraps

from flask import g, jsonify, make_response, render_template, request

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
        if self.response is None and result is not None:
            self._response = make_response(result)
        if self.response is None and self._action_depth == 1:
            self.render()
        return self.response

    action = decorate_action(
        cls, invoke, performed=lambda controller: controller.response is not None
    )

    @wraps(action)
    def wrapper(self, *args, **kwargs):
        outermost = getattr(self, "_action_depth", 0) == 0
        if outermost:
            self._action_name = action.__name__
            self._response = None
            self._action_depth = 0
        self._action_depth += 1
        try:
            result = action(self, *args, **kwargs)
            if self.response is None and result is not None:
                self._response = make_response(result)
            if self.response is None and outermost:
                self.render()
            return self.response
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


def head(status=200, headers=None):
    res = make_response("", status)
    if headers:
        res.headers.update(headers)
    return res


class ActionController:
    __slots__ = (
        "_params",
        "_response",
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
        return getattr(self, "_response", None)

    def respond_to(self, *, html=None, json=None):
        if self.response is not None:
            raise DoubleRenderError("This controller has already prepared a response.")
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
            self._response = make_response("406 Not Acceptable", 406)
        else:
            result = handler()
            if self.response is None and result is not None:
                self._response = make_response(result)
            if self.response is None and mime == "application/json":
                raise ProgrammerError(
                    "A JSON handler must render or return a response."
                )
        return self.response

    def render(self, action=None, *, status=200, json=_UNSET):
        if self.response is not None:
            raise DoubleRenderError("This controller has already prepared a response.")
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
        self._response = response
        return response
