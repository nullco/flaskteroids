"""Collect transport input before applying controller strong parameters."""

import re
from collections.abc import Callable

from flask import current_app, request
from werkzeug.exceptions import BadRequest

from flaskteroids._method_override import FORM_PAIRS
from flaskteroids.declarations import actions_for, model_for
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.inflector import inflector
from flaskteroids.rules import declaration


@declaration
def wrap_parameters(setting: bool | str = True) -> Callable[[type], None]:
    """Configure JSON root wrapping for a controller and its descendants."""
    if not isinstance(setting, (bool, str)) or (
        isinstance(setting, str) and not setting.strip()
    ):
        raise ProgrammerError(
            "wrap_parameters() expects True, False, or a nonempty root name."
        )

    def bind(cls: type) -> None:
        actions_for(cls).wrap_parameters = setting

    return bind


def request_parameters(controller, path_values):
    if request.is_json:
        data = request.get_json() if request.get_data(cache=True) else {}
        body = data if isinstance(data, dict) else {"_json": data}
        body = _wrap_json(controller, body)
    else:
        pairs = request.environ.get(FORM_PAIRS)
        if pairs is None:
            pairs = [*request.form.items(multi=True), *request.files.items(multi=True)]
        body = _unflatten_params(pairs)
    values = {
        **body,
        **_unflatten_params(request.args.to_dict(False)),
        **path_values,
    }
    values.pop("csrf_token", None)
    return values


def _wrap_json(controller, body):
    setting = actions_for(type(controller)).wrap_parameters
    if not setting:
        return body
    name = inflector.singularize(
        inflector.underscore(type(controller).__name__.removesuffix("Controller"))
    )
    root = setting if isinstance(setting, str) else name
    if root in body:
        return body
    model = current_app.extensions["flaskteroids.db"].models.get(
        inflector.camelize(name)
    )
    excluded = {"_json", "_method", "csrf_token", "authenticity_token", "utf8"}
    if model is None:
        attributes = set(body) - excluded
    else:
        model.prepare()
        definition = model_for(model)
        attributes = (
            set(model.__table__.columns.keys())
            | definition.attachments.keys()
            | definition.rich_texts.keys()
            | {f"{name}_attributes" for name in definition.nested_attributes}
            | {
                name
                for name, field in definition.virtual_fields.items()
                if not field.get("read_only")
            }
        ) - excluded
    return {
        **body,
        root: {key: value for key, value in body.items() if key in attributes},
    }


def _unflatten_params(flat_dict):
    def insert(container, keys, value, *, indexed):
        key = keys[0]
        is_last = len(keys) == 1
        if key == "":
            if not isinstance(container, list):
                raise BadRequest("Conflicting parameter shapes.")
            if is_last:
                container.append(value)
            else:
                if len(container) == 0 or not isinstance(container[-1], (dict, list)):
                    container.append({})
                container[-1] = insert(container[-1], keys[1:], value, indexed=indexed)
            return container
        if isinstance(container, list):
            if not indexed or not key.isdecimal():
                raise BadRequest("Conflicting parameter shapes.")
            index = int(key)
            while len(container) <= index:
                container.append({})
            if is_last:
                container[index] = value
            else:
                container[index] = insert(
                    container[index], keys[1:], value, indexed=indexed
                )
            return container
        if is_last:
            container[key] = value
        else:
            if key not in container or container[key] is None:
                next_key = keys[1]
                container[key] = (
                    []
                    if next_key == "" or (indexed and re.fullmatch(r"\d+", next_key))
                    else {}
                )
            elif not isinstance(container[key], (dict, list)):
                raise BadRequest("Conflicting parameter shapes.")
            container[key] = insert(container[key], keys[1:], value, indexed=indexed)
        return container

    result = {}
    entries = flat_dict.items() if isinstance(flat_dict, dict) else flat_dict
    for flat_key, value in entries:
        parts = re.findall(r"\w+|\[\]", flat_key)
        if not parts:
            continue
        keys = [parts[0]] + [part if part != "[]" else "" for part in parts[1:]]
        if isinstance(value, list):
            values = value if keys[-1] == "" else value[-1:]
        else:
            values = [value]
        for entry in values:
            result = insert(result, keys, entry, indexed=keys[0] != "_method")
    return result
