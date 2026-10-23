"""Persisted model references in captured mailer assigns."""

from flask import current_app
from sqlalchemy import inspect

from flaskteroids.exceptions import (
    DeserializationError,
    ProgrammerError,
    RecordNotFoundException,
    SerializationError,
)
from flaskteroids.model import Model

_TAG = "_flaskteroids_mail_value"


def serialize(value):
    if isinstance(value, Model):
        if not value.is_persisted() or inspect(value).identity is None:
            raise SerializationError("Save model assigns before queuing mail.")
        try:
            current_app.extensions["flaskteroids.db"].require_model(type(value))
        except ProgrammerError as error:
            raise SerializationError(str(error)) from error
        return {_TAG: ["model", type(value).__name__, list(inspect(value).identity)]}
    if isinstance(value, dict):
        result = {key: serialize(item) for key, item in value.items()}
        return {_TAG: ["mapping", result]} if _TAG in value else result
    if isinstance(value, tuple):
        return {_TAG: ["tuple", [serialize(item) for item in value]]}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value


def deserialize(value):
    if isinstance(value, list):
        return [deserialize(item) for item in value]
    if not isinstance(value, dict):
        return value
    if _TAG not in value:
        return {key: deserialize(item) for key, item in value.items()}
    tagged = value[_TAG]
    if set(value) != {_TAG} or not isinstance(tagged, list) or not tagged:
        raise DeserializationError("Invalid captured mailer value.")
    match tagged:
        case ["model", str(name), list(identity)] if identity:
            models = current_app.extensions["flaskteroids.db"].models
            if name not in models:
                raise DeserializationError(f"Mailer model {name!r} is not registered.")
            try:
                return models[name].find(tuple(identity))
            except (RecordNotFoundException, ValueError) as error:
                raise DeserializationError(
                    f"Cannot restore mailer model {name!r} with identity {identity!r}."
                ) from error
        case ["mapping", dict(items)]:
            return {key: deserialize(item) for key, item in items.items()}
        case ["tuple", list(items)]:
            return tuple(deserialize(item) for item in items)
        case _:
            raise DeserializationError("Invalid captured mailer value.")
