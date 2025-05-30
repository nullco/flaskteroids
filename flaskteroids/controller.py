from functools import wraps
from flask import redirect, render_template
from flaskteroids.actions import decorate_action, get_actions, ParamsProxy, register_actions
from flaskteroids.exceptions import Redirect
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
        cname = self.__class__.__name__.replace("Controller", "").lower()
        view_template = render_template(f'{cname}/{action.__name__}.html', **{**self.__dict__, 'params': params})
        return view_template
    return wrapper


class ActionController:
    pass


params = ParamsProxy()


def redirect_to(url):
    raise Redirect(redirect(url))
