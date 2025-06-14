import logging
import re
from werkzeug.local import LocalProxy
from functools import wraps
from typing import Any
from collections import UserDict, defaultdict
from flask import g
from flaskteroids import registry
from flaskteroids.exceptions import InvalidParameter, MissingParameter, ProgrammerError
from flaskteroids.discovery import discover_methods


_logger = logging.getLogger(__name__)


def register_actions(cls, base_cls):
    ns = registry.get(cls)
    ns['actions'] = discover_methods(
        cls, ignore=set(discover_methods(base_cls))
    )


def get_actions(cls):
    ns = registry.get(cls)
    return ns.get('actions') or []


def decorate_action(cls, action_fn):
    @wraps(action_fn)
    def wrapper(*args, **kwargs):
        ns = registry.get(cls)
        before_action = [getattr(cls, ba) for ba in ns.get('before_action', {}).get(action_fn.__name__, [])]
        for ba in before_action:
            res = ba(*args, **kwargs)
            if res:
                return res
        around_action = [
            getattr(cls, aa)(*args, **kwargs)
            for aa in ns.get('around_action', {}).get(action_fn.__name__, [])
        ]
        for aa in around_action:
            next(aa)
        res = action_fn(*args, **kwargs)
        for aa in reversed(around_action):
            next(aa, None)
        after_action = [getattr(cls, aa) for aa in ns.get('after_action', {}).get(action_fn.__name__, [])]
        for aa in after_action:
            aa(*args, **kwargs)
        return res
    return wrapper


def before_action(method_name: str, *, only=None):
    def bind(cls):
        if not method_name.startswith('_'):
            raise ProgrammerError('Before action methods should follow conventions for private methods')
        getattr(cls, method_name)
        actions = only if only else None
        ns = registry.get(cls)

        if 'before_action' not in ns:
            ns['before_action'] = defaultdict(lambda: [])
        if not actions:
            actions = ns['actions'] if 'actions' in ns else []

        for action_name in actions:
            _logger.debug(f'before_action: setting {method_name} before {action_name} on {cls.__name__}')
            ns['before_action'][action_name].append(method_name)
    return bind


def around_action(method_name: str, *, only=None):
    def bind(cls):
        if not method_name.startswith('_'):
            raise ProgrammerError('Around action methods should follow conventions for private methods')
        getattr(cls, method_name)
        actions = only if only else None
        ns = registry.get(cls)

        if 'around_action' not in ns:
            ns['around_action'] = defaultdict(lambda: [])
        if not actions:
            actions = ns['actions'] if 'actions' in ns else []

        for action_name in actions:
            _logger.debug(f'around_action: setting {method_name} around {action_name} on {cls.__name__}')
            ns['around_action'][action_name].append(method_name)
    return bind


def after_action(method_name: str, *, only=None):
    def bind(cls):
        if not method_name.startswith('_'):
            raise ProgrammerError('After action methods should follow conventions for private methods')
        getattr(cls, method_name)
        actions = only if only else None
        ns = registry.get(cls)

        if 'after_action' not in ns:
            ns['after_action'] = defaultdict(lambda: [])
        if not actions:
            actions = ns['actions'] if 'actions' in ns else []

        for action_name in actions:
            _logger.debug(f'after_action: setting {method_name} after {action_name} on {cls.__name__}')
            ns['after_action'][action_name].append(method_name)
    return bind


def skip_before_action(method_name: str, *, only=None):
    def bind(cls):
        ns = registry.get(cls)
        actions = only if only else None
        if not actions:
            actions = ns['actions'] if 'actions' in ns else []
        for action_name in actions:
            if 'before_action' not in ns:
                continue
            if action_name not in ns['before_action']:
                continue
            if method_name not in ns['before_action'][action_name]:
                continue
            ns['before_action'][action_name].remove(method_name)
    return bind


class ActionParameters(UserDict):

    @classmethod
    def new(cls, params):
        p = ActionParameters()
        p.update(params)
        return p

    def expect(self, *args, **kwargs):
        root = {}
        for arg in args:
            schema = self._schema('params', [arg])
            root.update(self._expect('params', self.data, schema))
        expected = [root] if root else []
        for k, v in kwargs.items():
            schema = self._schema(f'params.{k}', [(k, v)])
            res = self._expect(f'params.{k}', self.data, schema)
            expected.append(res[k])
        if not expected:
            return {}
        elif len(expected) == 1:
            return expected[0]
        else:
            return expected

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


def _get_params():
    if 'params' not in g:
        g.params = ActionParameters()
    return g.params


params = LocalProxy(_get_params)
