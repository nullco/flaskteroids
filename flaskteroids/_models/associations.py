from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterator
from functools import partial
from typing import TYPE_CHECKING, Any

from flask import current_app
from sqlalchemy import event, inspect, select

from flaskteroids._models.records import _base, _build
from flaskteroids.db import session
from flaskteroids.declarations import AssociationDefinition, model_for
from flaskteroids.exceptions import ProgrammerError, RecordNotFoundException
from flaskteroids.inflector import inflector

if TYPE_CHECKING:
    from flaskteroids.extensions.db import ResolvedAssociation, SQLAlchemyExtension
    from flaskteroids.model import Model


def _check_declaration(name, target, foreign_key, dependent=None):
    if not all(
        isinstance(value, str) and value for value in (name, target, foreign_key)
    ):
        raise ProgrammerError(
            "Association names, targets and foreign keys must be nonempty strings."
        )
    if dependent not in (None, "destroy"):
        raise ProgrammerError(
            f"Unsupported association dependent option: {dependent!r}"
        )


def belongs_to(
    name: str, class_name: str | None = None, foreign_key: str | None = None
) -> Callable[[type[Model]], None]:
    def bind(cls: type[Model]) -> None:
        _check_declaration(
            name,
            class_name if class_name is not None else name,
            foreign_key if foreign_key is not None else name,
        )
        target = class_name if class_name is not None else inflector.camelize(name)
        fk_name = (
            foreign_key if foreign_key is not None else inflector.foreign_key(target)
        )
        _check_declaration(name, target, fk_name)
        definition = model_for(cls)
        definition.associations[name] = AssociationDefinition(
            name, "belongs_to", target, fk_name
        )

        def rel_wrapper(self):
            association = _get_association(self.__class__, name=name)
            if name in self._changes:
                return self._changes[name]
            value = getattr(self, fk_name)
            related = _load_one(self._base_instance, association, value)
            return _build(association.target, related) if related is not None else None

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
        association = _get_association(self._instance.__class__, name=self._name)
        base = self._instance._base_instance
        cache = _association_cache()
        key = (base, self._name)
        identity = self._instance.id
        if key not in cache or cache[key][0] != identity:
            target = _base(self._related_cls)
            entries = (
                list(
                    session.scalars(
                        select(target).where(
                            getattr(target, association.foreign_key) == identity
                        )
                    )
                )
                if identity is not None
                else []
            )
            cache[key] = identity, entries
            _cache_inverse(base, association, entries)
        return cache[key][1]

    def __len__(self) -> int:
        return len(self._entries())

    def __iter__(self) -> Iterator[RelatedModel]:
        for entry in self._entries():
            yield _build(self._related_cls, entry)

    def __repr__(self) -> str:
        return repr(list(self))

    def create(self, **kwargs) -> RelatedModel:
        association = _get_association(self._instance.__class__, name=self._name)
        if self._instance.is_new_record():
            if not self._instance.save():
                raise ProgrammerError(
                    "Cannot create a related record for an unsaved invalid parent."
                )
        kwargs.setdefault(association.foreign_key, self._instance.id)
        related_instance = self._related_cls.new(**kwargs)
        if related_instance.save():
            self._instance.save()
        return related_instance


def has_many(
    name: str,
    class_name: str | None = None,
    foreign_key: str | None = None,
    dependent: str | None = None,
) -> Callable[[type[Model]], None]:
    def bind(cls: type[Model]) -> None:
        _check_declaration(
            name,
            class_name if class_name is not None else name,
            foreign_key if foreign_key is not None else name,
            dependent,
        )
        target = (
            class_name
            if class_name is not None
            else inflector.camelize(inflector.singularize(name))
        )
        fk_name = (
            foreign_key
            if foreign_key is not None
            else inflector.foreign_key(cls.__name__)
        )
        _check_declaration(name, target, fk_name, dependent)
        model_for(cls).associations[name] = AssociationDefinition(
            name, "has_many", target, fk_name, dependent
        )

        def rel_wrapper(self):
            association = _get_association(self.__class__, name=name)
            return Relation(self, association.target, association.name)

        setattr(cls, name, property(rel_wrapper))

    return bind


def _clear_association_cache(db_session, *args):
    db_session.info.pop("flaskteroids.associations", None)


def _association_cache():
    db_session = session._get_current_object()
    if not db_session.info.get("flaskteroids.association_listeners"):
        for name in (
            "before_flush",
            "after_commit",
            "after_rollback",
            "after_soft_rollback",
        ):
            event.listen(db_session, name, _clear_association_cache)
        db_session.info["flaskteroids.association_listeners"] = True
    return db_session.info.setdefault("flaskteroids.associations", {})


def _load_one(base, association, identity):
    cache = _association_cache()
    key = base, association.name
    if key not in cache or cache[key][0] != identity:
        target = _base(association.target)
        pk = inspect(target).primary_key
        if identity is None:
            related = None
        elif len(pk) == 1 and pk[0].key == "id":
            related = session.get(target, identity)
        else:
            related = session.scalars(
                select(target).where(target.id == identity)
            ).first()
        cache[key] = identity, related
    return cache[key][1]


def _cache_inverse(base, association, entries):
    if association.inverse is not None and association.kind == "has_many":
        cache = _association_cache()
        for related in entries:
            cache[related, association.inverse] = base.id, base


def _preload(model_cls, records, names):
    """Batch association queries without adding properties to live row mappers."""
    if not records:
        return
    for name in names:
        association = _get_association(model_cls, name=name)
        target = _base(association.target)
        source_key = (
            association.foreign_key if association.kind == "belongs_to" else "id"
        )
        target_key = (
            "id" if association.kind == "belongs_to" else association.foreign_key
        )
        identities = list({getattr(record, source_key) for record in records} - {None})
        grouped = defaultdict(list)
        for offset in range(0, len(identities), 500):
            query = select(target).where(
                getattr(target, target_key).in_(identities[offset : offset + 500])
            )
            for related in session.scalars(query):
                grouped[getattr(related, target_key)].append(related)
        cache = _association_cache()
        for record in records:
            identity = getattr(record, source_key)
            entries = grouped[identity]
            value = (
                (entries[0] if entries else None)
                if association.kind == "belongs_to"
                else entries
            )
            cache[record, name] = identity, value
            _cache_inverse(record, association, entries)


def _destroy_associations(instance):
    for definition in model_for(type(instance)).associations.values():
        if definition.kind != "has_many":
            continue
        relation = getattr(instance, definition.name)
        if definition.dependent == "destroy":
            for child in list(relation):
                if not child.destroy():
                    return False
        else:
            for child in relation._entries():
                setattr(child, definition.foreign_key, None)
            session.flush()
    return True


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
    try:
        association.target.find(value)
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
    return db.association(model_cls, definition.name)
