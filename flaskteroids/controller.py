from functools import wraps
from flask import render_template, request, make_response, g, jsonify
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
        return render(action.__name__)
    return wrapper


class FormatResponder:
    def __init__(self, *, html=None, json=None):
        self._handlers = {
            'text/html': html,
            'application/json': json
        }

    def _get_accepts(self):
        if request.path.endswith('.json/'):
            return 'application/json'
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
        cname = inflector.underscore(g.controller.__class__.__name__.replace("Controller", ""))
        view = render_template(f'{cname}/{action}.html', **{**g.controller.__dict__, 'params': params})
        return make_response(view, status)
    elif json:
        return jsonify(json.__json__())


def head(status=200, headers=None):
    res = make_response('', status)
    if headers:
        res.headers.update(headers)
    return res


def respond(**kwargs):
    formatter = FormatResponder(**kwargs)
    return formatter.handle()


class ActionController:
    def __init__(self, *args, **kwargs) -> None:
        g.controller = self
