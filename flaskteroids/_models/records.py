from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import current_app

from flaskteroids.callbacks import run_callbacks

if TYPE_CHECKING:
    from flaskteroids.extensions.db import SQLAlchemyExtension
    from flaskteroids.model import Model


def _build[RecordModel: "Model"](
    model_cls: type[RecordModel], base_instance: Any
) -> RecordModel:
    res = object.__new__(model_cls)
    res._initialize()
    res._base_instance = base_instance
    run_callbacks(res, "initialize", None, lambda: None)
    run_callbacks(res, "find", None, lambda: None)
    return res


def _base(model_cls: type[Model]) -> type:
    db: SQLAlchemyExtension = current_app.extensions["flaskteroids.db"]
    return db.binding(model_cls).mapped_class
