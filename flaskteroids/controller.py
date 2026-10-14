from functools import wraps

from flask import g, jsonify, make_response, render_template, request

from flaskteroids.actions import (
    decorate_action,
    get_actions,
    mark_action_wrapper,
    original_action,
    params,
    register_actions,
)
from flaskteroids.declarations import actions_for
from flaskteroids.inflector import inflector
from flaskteroids.rules import bind_rules


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
    action = decorate_action(cls, action)

    @wraps(action)
    def wrapper(self, *args, **kwargs):
        res = action(self, *args, **kwargs)
        if res is not None:
            return res
        return render(action.__name__)

    return mark_action_wrapper(wrapper, original)


class FormatResponder:
    def __init__(self, *, html=None, json=None):
        self._handlers = {"text/html": html, "application/json": json}

    def _get_accepts(self):
        if request.path.endswith(".json/"):
            return "application/json"
        accept_mimetypes = request.accept_mimetypes
        accepts = accept_mimetypes.best_match(self._handlers.keys()) or "text/html"
        return accepts

    def handle(self):
        handler = self._handlers.get(self._get_accepts())
        if handler:
            return handler()
        else:
            return "406 Not Acceptable", 406


def render(action=None, *, status=200, json=None):
    if action:
        cname = inflector.underscore(
            g.controller.__class__.__name__.replace("Controller", "")
        )
        view = render_template(
            f"{cname}/{action}.html", **{**g.controller.__dict__, "params": params}
        )
        return make_response(view, status)
    else:
        return make_response(jsonify(_serialize_json(json)), status)


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


def respond(**kwargs):
    formatter = FormatResponder(**kwargs)
    return formatter.handle()


class ActionController:
    def __init__(self, *args, **kwargs) -> None:
        g.controller = self
