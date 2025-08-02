from functools import wraps
from flask import render_template, request, make_response 
from flaskteroids.actions import decorate_action, get_actions, register_actions, params
from flaskteroids.rules import bind_rules
from flaskteroids.inflector import inflector


def init(cls):
    register_actions(cls, ActionController)
    bind_rules(cls)
    _decorate_actions(cls)
    return cls


def _decorate_actions(cls):
    for name in get_actions(cls):
        action = getattr(cls, name)
        setattr(cls, name, _decorate_action(cls, action))


def _decorate_action(cls, action):
    action = decorate_action(cls, action)

    @wraps(action)
    def wrapper(self, *args, **kwargs):
        res = action(self, *args, **kwargs)
        if res:
            return res
        return self.render(action.__name__)
    return wrapper


class FormatResponder:
    def __init__(self):
        self._handlers = {}

    def html(self, func):
        self._handlers["text/html"] = func

    def json(self, func):
        self._handlers["application/json"] = func

    def respond(self):
        content_type = request.headers.get("Accept", "text/html")
        handler = self._handlers.get(content_type)
        if handler:
            return handler()
        else:
            return "406 Not Acceptable", 406


class ActionController:

    def respond_to(self):
        return FormatResponder()

    def render(self, action=None, *, status=200, json=None):
        if action:
            cname = inflector.underscore(self.__class__.__name__.replace("Controller", ""))
            view = render_template(f'{cname}/{action}.html', **{**self.__dict__, 'params': params})
            return make_response(view, status)
        elif json:
            return json
