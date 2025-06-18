from functools import wraps
from flask import render_template, request
from flaskteroids.actions import decorate_action, get_actions, register_actions, params
from flaskteroids.rules import bind_rules


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


class ActionController:

    @classmethod
    def respond_to(cls, *, html=None, json=None):
        if request.accept_mimetypes.accept_html:
            return html() if html else None
        elif json and request.accept_mimetypes.accept_json:
            return json()

    def render(self, action=None, *, json=None):
        if action:
            cname = self.__class__.__name__.replace("Controller", "").lower()
            view = render_template(f'{cname}/{action}.html', **{**self.__dict__, 'params': params})
            return view
        elif json:
            return json




