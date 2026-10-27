"""Shared controller lifecycle, independent of browser rendering."""

from functools import wraps

from flask import current_app, g, jsonify, make_response, redirect
from werkzeug.wrappers import Response as BaseResponse

from flaskteroids._request_policy import BROWSER_REQUESTS
from flaskteroids.actions import (
    Parameters,
    decorate_action,
    get_actions,
    mark_action_wrapper,
    original_action,
    register_actions,
)
from flaskteroids.declarations import actions_for
from flaskteroids.exceptions import DoubleRenderError, ProgrammerError
from flaskteroids.i18n import localize, translate
from flaskteroids.inflector import inflector
from flaskteroids.routes import _polymorphic_path
from flaskteroids.rules import bind_rules

_UNSET = object()


def prepare_controller(cls, base):
    definition = actions_for(cls)
    if definition.prepared:
        return cls
    register_actions(cls, base)
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
            self._default_render()
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
            self._response_mime = None
        self._action_depth += 1
        try:
            result = action(self, *args, **kwargs)
            if not self.performed and result is not None:
                self._prepare_response(result)
            if not self.performed and outermost:
                self._default_render()
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


class ControllerBase:
    _request_policy = BROWSER_REQUESTS

    @classmethod
    def _prepare_views(cls, helpers):
        pass

    __slots__ = (
        "_params",
        "_response",
        "_performed",
        "_action_name",
        "_action_depth",
        "_response_mime",
        "__dict__",
        "__weakref__",
    )

    def __init__(self, *args, **kwargs) -> None:
        g.controller = self

    @property
    def params(self) -> Parameters:
        if not hasattr(self, "_params"):
            self._params = Parameters()
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
        self._inherit_response_metadata(response)
        supplied = {name.lower() for name in response.headers.keys()}
        for name, value in self.response.headers:
            if name.lower() not in supplied:
                response.headers.add(name, value)
        self._response = response
        self._performed = True
        return response

    def translate(self, key, **options):
        if isinstance(key, str) and key.startswith(".") and "scope" not in options:
            action = getattr(self, "_action_name", None)
            if not action:
                raise ProgrammerError("Relative translations require a current action.")
            controller = inflector.underscore(
                type(self).__name__.removesuffix("Controller")
            )
            options["scope"] = f"{controller}.{action}"
        return translate(key, **options)

    t = translate
    localize = staticmethod(localize)
    l = localize  # noqa: E741 - Rails-compatible localization alias.

    def redirect_to(self, target, *, status=302):
        self._ensure_response_available()
        if target is None:
            raise ProgrammerError("redirect_to() requires a destination.")
        response = redirect(target, code=status or 302)
        response.set_data("")
        return self._prepare_response(response)

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

    def _default_render(self):
        raise NotImplementedError

    def _inherit_response_metadata(self, response):
        pass

    def _response_variant(self):
        return None

    def render(self, *, json=_UNSET, status=_UNSET, location=None):
        self._ensure_response_available()
        if json is _UNSET:
            raise ProgrammerError("Specify json= or return an explicit response.")
        status = self.response.status_code if status is _UNSET else status
        response = make_response(jsonify(_serialize_json(json)), status)
        if location is not None:
            response.headers["Location"] = (
                location if isinstance(location, str) else _polymorphic_path(location)
            )
        return self._prepare_response(response)
