import logging
from typing import Any
from collections import UserDict, defaultdict
from collections.abc import MutableMapping
from flask import redirect, render_template, g
from flaskteroids import registry
from flaskteroids.exceptions import InvalidParameter, MissingParameter, ProgrammerError, Redirect


_logger = logging.getLogger(__name__)


def before_action(method_name, *, only=None):
    def register(controller_cls):
        actions = only if only else None
        ns = registry.get(controller_cls)

        if 'before_action' not in ns:
            ns['before_action'] = defaultdict(lambda: [])
        if not actions:
            actions = ns['actions'] if 'actions' in ns else []

        for action_name in actions:
            _logger.debug(f'before_action: setting {method_name} before {action_name} on {controller_cls.__name__}')
            ns['before_action'][action_name].append(method_name)
    return register


def _chain(*actions):
    def wrapper(*args, **kwargs):
        res = None
        for action in actions:
            res = action(*args, **kwargs)
            if res:
                break
        return res
    return wrapper


class ActionController:

    def __getattr__(self, name):
        if name.startswith('invoke_'):
            name = name.replace('invoke_', '')

            def wrapper(*args, **kwargs):
                ns = registry.get(self.__class__)
                before_action = [ba for ba in ns.get('before_action', {}).get(name, [])]
                before_action = [getattr(self, ba) for ba in before_action]
                action = _chain(*before_action, getattr(self, name))
                res = action(*args, **kwargs)
                if res:
                    return res
                cname = self.__class__.__name__.replace("Controller", "").lower()
                view_template = render_template(f'{cname}/{name}.html', **self.__dict__)
                return view_template
            return wrapper

        raise AttributeError(f"{self.__class__.__name__} does not have attribute {name}")


class ActionParameters(UserDict):

    @classmethod
    def new(cls, params):
        p = ActionParameters()
        p.update(params)
        return p

    def expect(self, fields):
        schema = self._schema('params', fields)
        return self._expect('params', self.data, schema)

    def _schema(self, key, fields):
        if not isinstance(fields, list):
            raise ProgrammerError(key, 'Incorrect fields specification. Fields should always be lists')
        schema = {}
        for f in fields:
            if isinstance(f, str):
                schema[f] = Any
            elif isinstance(f, tuple) and len(f) == 2:
                fk, fv = f
                if isinstance(fv, list) and len(fv) == 0:
                    schema[fk] = list
                elif isinstance(fv, list) and len(fv) == 1 and isinstance(fv[0], list):
                    schema[fk] = [self._schema(fk, fv[0])]
                else:
                    schema[fk] = self._schema(fk, fv)
            else:
                raise ProgrammerError(key, 'Incorrect field specification. Field must be str / tuple')
        return schema

    def _expect(self, key, value, schema):
        if not isinstance(value, dict):
            raise InvalidParameter(key, 'Invalid parameter type. Not a dict')
        expected = {}
        for k, v in schema.items():
            if k not in value:
                raise MissingParameter(key, k, 'Parameter is missing')
            elif value[k] is None:
                expected[k] = None
            elif v is Any:
                if type(value[k]) not in (int, float, str, bool):
                    raise InvalidParameter(key, k, 'Invalid parameter type. Not a scalar')
                expected[k] = value[k]
            elif v is list:
                if not isinstance(value[k], list):
                    raise InvalidParameter(key, k, 'Invalid parameter type. Not a list')
                if any(type(vi) not in (int, float, str, bool) for vi in value[k]):
                    raise InvalidParameter(key, k, 'Invalid parameter type. Not a scalars list')
                expected[k] = value[k]
            elif isinstance(v, list):
                if not isinstance(value[k], list):
                    raise InvalidParameter(key, k, 'Invalid parameter type. Not a list')
                expected[k] = [self._expect(f'{key}.{k}[{i}]', vi, v[0]) for i, vi in enumerate(value[k])]
            elif isinstance(v, dict):
                if not isinstance(value[k], dict):
                    raise InvalidParameter(key, k, 'Invalid parameter type. Not a dict')
                expected[k] = self._expect(f'{key}.{k}', value[k], v)
        return expected

    def __str__(self) -> str:
        return str(g.params)


class ParamsProxy(MutableMapping):

    def __getattr__(self, name):
        self._ensure_params()
        return getattr(g.params, name)

    def __getitem__(self, key):
        self._ensure_params()
        return g.params[key]

    def __setitem__(self, key, val):
        self._ensure_params()
        g.params[key] = val

    def __delitem__(self, key):
        self._ensure_params()
        del g.params[key]

    def __iter__(self):
        self._ensure_params()
        return iter(g.params)

    def __len__(self):
        self._ensure_params()
        return len(g.params)

    def _ensure_params(self):
        if 'params' not in g:
            g.params = ActionParameters()


params = ParamsProxy()


def redirect_to(url):
    raise Redirect(redirect(url))
