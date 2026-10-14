import logging
from collections import UserDict
from functools import wraps
from typing import Any, Literal

from flask import g
from werkzeug.datastructures import FileStorage
from werkzeug.local import LocalProxy

from flaskteroids.declarations import actions_for
from flaskteroids.discovery import discover_methods
from flaskteroids.exceptions import InvalidParameter, MissingParameter, ProgrammerError

_logger = logging.getLogger(__name__)


def register_actions(cls, base_cls):
    definition = actions_for(cls)
    definition.names = discover_methods(cls, ignore=set(discover_methods(base_cls)))
    for name in definition.names:
        action = getattr(cls, name)
        if getattr(action, "_flaskteroids_wrapper", None) is action:
            action = action._flaskteroids_original
        definition.originals[name] = action


def get_actions(cls):
    return actions_for(cls).names


def original_action(cls, name):
    return actions_for(cls).originals[name]


def mark_action_wrapper(wrapper, original):
    wrapper._flaskteroids_original = original
    wrapper._flaskteroids_wrapper = wrapper
    return wrapper


def decorate_action(cls, action_fn):
    @wraps(action_fn)
    def wrapper(*args, **kwargs):
        definition = actions_for(cls)
        before_action = [
            getattr(cls, ba) for ba in definition.before.get(action_fn.__name__, [])
        ]
        for ba in before_action:
            res = ba(*args, **kwargs)
            if res:
                return res
        generators = []
        original_error = None
        try:
            for name in definition.around.get(action_fn.__name__, []):
                generator = getattr(cls, name)(*args, **kwargs)
                try:
                    next(generator)
                except StopIteration as stopped:
                    return stopped.value
                generators.append((name, generator))
            res = action_fn(*args, **kwargs)
        except BaseException as exc:
            original_error = exc
            raise
        finally:
            _finalize_around(generators, original_error)
        after_action = [
            getattr(cls, aa) for aa in definition.after.get(action_fn.__name__, [])
        ]
        for aa in after_action:
            aa(*args, **kwargs)
        return res

    return wrapper


def _finalize_around(generators, original_error):
    error = original_error
    for name, generator in reversed(generators):
        try:
            try:
                next(generator)
            except StopIteration:
                pass
            else:
                raise ProgrammerError(f"Around action <{name}> must yield exactly once")
            finally:
                generator.close()
        except BaseException as exc:
            if error is None:
                error = exc
            else:
                error.add_note(f"Around-action cleanup <{name}> failed: {exc!r}")
                _logger.exception("Around-action cleanup <%s> failed", name)
    if original_error is None and error is not None:
        raise error


def _register_action(
    cls: type,
    method_name: str,
    *,
    only,
    kind: Literal["before", "around", "after"],
) -> None:
    if not method_name.startswith("_"):
        raise ProgrammerError(
            f"{kind.capitalize()} action methods should follow conventions for private methods"
        )
    getattr(cls, method_name)
    actions = only if only else None
    definition = actions_for(cls)
    if not actions:
        actions = definition.names

    if kind == "before":
        chain = definition.before
    elif kind == "around":
        chain = definition.around
    else:
        chain = definition.after

    for action_name in actions:
        _logger.debug(
            f"{kind}_action: setting {method_name} {kind} {action_name} on {cls.__name__}"
        )
        chain.setdefault(action_name, []).append(method_name)


def before_action(method_name: str, *, only=None):
    def bind(cls):
        _register_action(cls, method_name, only=only, kind="before")

    return bind


def around_action(method_name: str, *, only=None):
    def bind(cls):
        _register_action(cls, method_name, only=only, kind="around")

    return bind


def after_action(method_name: str, *, only=None):
    def bind(cls):
        _register_action(cls, method_name, only=only, kind="after")

    return bind


def skip_before_action(method_name: str, *, only=None):
    def bind(cls):
        definition = actions_for(cls)
        actions = only or definition.names
        for action_name in actions:
            chain = definition.before.get(action_name, [])
            if method_name in chain:
                chain.remove(method_name)

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
            schema = self._schema("params", [arg])
            root.update(self._require("params", self.data, schema))
        expected = [root] if root else []
        for k, v in kwargs.items():
            schema = self._schema(f"params.{k}", [(k, v)])
            res = self._require("params", self.data, schema)
            expected.append(res[k])
        if not expected:
            return {}
        elif len(expected) == 1:
            return expected[0]
        else:
            return expected

    def _schema(self, key, fields):
        if not isinstance(fields, list):
            raise ProgrammerError(
                key, "Incorrect fields specification. Fields should always be lists"
            )
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
                raise ProgrammerError(
                    key, "Incorrect field specification. Field must be str / tuple"
                )
        return schema

    def _require(self, key, value, schema):
        expected = self._expect(key, value, schema)
        for name in schema:
            result = expected.get(name)
            if (
                result is None
                or (isinstance(result, str) and not result.strip())
                or (isinstance(result, (dict, list)) and not result)
            ):
                raise MissingParameter(key, name, "Parameter is missing or empty")
        return expected

    def _expect(self, key, value, schema):
        if not isinstance(value, dict):
            raise InvalidParameter(key, "Invalid parameter type. Not a dict")
        expected = {}
        for k, v in schema.items():
            if k not in value:
                continue
            elif value[k] is None:
                expected[k] = None
            elif v is Any:
                if type(value[k]) not in (int, float, str, bool) and not isinstance(
                    value[k], FileStorage
                ):
                    raise InvalidParameter(
                        key, k, "Invalid parameter type. Not a scalar"
                    )
                expected[k] = value[k]
            elif v is list:
                if not isinstance(value[k], list):
                    raise InvalidParameter(key, k, "Invalid parameter type. Not a list")
                if any(
                    type(vi) not in (int, float, str, bool)
                    and not isinstance(vi, FileStorage)
                    for vi in value[k]
                ):
                    raise InvalidParameter(
                        key, k, "Invalid parameter type. Not a scalars list"
                    )
                expected[k] = value[k]
            elif isinstance(v, list):
                if not isinstance(value[k], list):
                    raise InvalidParameter(key, k, "Invalid parameter type. Not a list")
                expected[k] = [
                    self._expect(f"{key}.{k}[{i}]", vi, v[0])
                    for i, vi in enumerate(value[k])
                ]
            elif isinstance(v, dict):
                if not isinstance(value[k], dict):
                    raise InvalidParameter(key, k, "Invalid parameter type. Not a dict")
                expected[k] = self._expect(f"{key}.{k}", value[k], v)
        return expected


def _get_params() -> ActionParameters:
    if "params" not in g:
        g.params = ActionParameters()
    return g.params


params = LocalProxy(_get_params)
