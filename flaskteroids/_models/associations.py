from __future__ import annotations

from collections.abc import Callable, Iterator
from functools import partial
from typing import TYPE_CHECKING, Any

from flask import current_app

from flaskteroids._models.records import _build
from flaskteroids.declarations import AssociationDefinition, model_for
from flaskteroids.exceptions import ProgrammerError, RecordNotFoundException
from flaskteroids.inflector import inflector

if TYPE_CHECKING:
    from flaskteroids.extensions.db import ResolvedAssociation, SQLAlchemyExtension
    from flaskteroids.model import Model


def belongs_to(
    name: str, class_name: str | None = None, foreign_key: str | None = None
) -> Callable[[type[Model]], None]:
    def bind(cls: type[Model]) -> None:
        target = class_name or inflector.camelize(name)
        fk_name = foreign_key or inflector.foreign_key(target)
        definition = model_for(cls)
        definition.associations[name] = AssociationDefinition(
            name, "belongs_to", target, fk_name
        )

        def rel_wrapper(self):
            association = _get_association(self.__class__, name=name)
            if association.name in self._changes:
                return self._changes[association.name]
            related_base_instance = getattr(self._base_instance, association.name)
            if related_base_instance is None:
                return None
            return _build(association.target, related_base_instance)

        setattr(cls, name, property(rel_wrapper))
        definition.validators.append(partial(_validate_fk, field=fk_name))

    return bind


class Relation[RelatedModel: "Model"]:
    def __init__(
        self, instance: Model, related_cls: type[RelatedModel], name: str
    ) -> None:
        self._instance = instance
        self._related_cls = related_cls
        self._name = name

    def _entries(self) -> list[Any]:
        return getattr(self._instance._base_instance, self._name)

    def __len__(self) -> int:
        return len(self._entries())

    def __iter__(self) -> Iterator[RelatedModel]:
        for v in self._entries():
            yield _build(self._related_cls, v)

    def __repr__(self) -> str:
        return repr([v for v in self])

    def create(self, **kwargs) -> RelatedModel:
        association = _get_association(self._instance.__class__, name=self._name)
        kwargs.setdefault(association.foreign_key, self._instance.id)
        related_instance = self._related_cls.new(**kwargs)
        entries = self._entries()
        if not related_instance.save():
            return related_instance
        if related_instance._base_instance not in entries:
            entries.append(related_instance._base_instance)
        self._instance.save()
        return related_instance


def has_many(
    name: str,
    class_name: str | None = None,
    foreign_key: str | None = None,
    dependent: str | None = None,
) -> Callable[[type[Model]], None]:
    def bind(cls: type[Model]) -> None:
        target = class_name or inflector.camelize(inflector.singularize(name))
        fk_name = foreign_key or inflector.foreign_key(cls.__name__)
        model_for(cls).associations[name] = AssociationDefinition(
            name, "has_many", target, fk_name, dependent
        )

        def rel_wrapper(self):
            association = _get_association(self.__class__, name=name)
            return Relation(self, association.target, association.name)

        setattr(cls, name, property(rel_wrapper))

    return bind


def _validate_fk(
    *, instance: Model, field: str, config: bool = True
) -> list[tuple[str, str]]:
    if not config:
        return []
    association = _get_association(instance.__class__, name=field)
    if not association:
        return []
    value = getattr(instance, field)
    if not value:
        return [(field, f"{association.name} must exist")]
    related_cls = association.target
    try:
        related_cls.find(value)
        return []
    except RecordNotFoundException:
        return [(field, f"{association.name} must exist")]


def _get_association(
    model_cls: type[Model], *, name: str
) -> ResolvedAssociation | None:
    definition = next(
        (
            entry
            for entry in model_for(model_cls).associations.values()
            if entry.name == name or entry.foreign_key == name
        ),
        None,
    )
    if definition is None:
        return None
    db: SQLAlchemyExtension = current_app.extensions["flaskteroids.db"]
    association = db.binding(model_cls).associations[definition.name]
    try:
        db.binding(association.target)
    except ProgrammerError as error:
        error.add_note(f"While using {model_cls.__name__}.{definition.name}")
        raise
    return association
