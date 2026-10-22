"""Class-body declarations translated to native relationships before mapping."""

from collections.abc import MutableSequence

from sqlalchemy import false, inspect
from sqlalchemy.orm import relationship, with_parent
from sqlalchemy.orm.attributes import NO_VALUE

from flaskteroids._models.query import ModelQuery
from flaskteroids.db import session
from flaskteroids.declarations import AssociationDefinition, model_for
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.inflector import inflector
from flaskteroids.rules import declaration


class AssociationQuery(ModelQuery):
    def __init__(self, owner, name):
        self.owner = owner
        self.name = name
        self.relationship = inspect(type(owner)).relationships[name]
        super().__init__(self.relationship.mapper.class_)
        self.statement = self.statement.where(
            false()
            if owner.is_new_record()
            else with_parent(owner, getattr(type(owner), name))
        )

    def new(self, **attributes):
        record = super().new(**attributes)
        for local, remote in self.relationship.local_remote_pairs:
            setattr(record, remote.key, getattr(self.owner, local.key))
        if inverse := self.relationship.back_populates:
            setattr(record, inverse, self.owner)
        return record

    def create(self, **attributes):
        if not self.owner.is_persisted():
            raise ProgrammerError("Save the parent before creating associated records.")
        record = super().create(**attributes)
        if record.is_persisted():
            loaded = inspect(self.owner).attrs[self.name].loaded_value
            if loaded is not NO_VALUE and record not in loaded:
                loaded.append(record)
        return record


class AssociationCollection(MutableSequence):
    """Application API over SQLAlchemy's collection, without a second cache."""

    def __init__(self, owner, name):
        self.owner = owner
        self.name = name

    def _collection(self):
        # Bypass the application-facing getter, not SQLAlchemy instrumentation.
        return object.__getattribute__(self.owner, self.name)

    def all(self):
        return AssociationQuery(self.owner, self.name)

    def where(self, *expressions, **filters):
        return self.all().where(*expressions, **filters)

    def new(self, **attributes):
        return self.all().new(**attributes)

    def create(self, **attributes):
        return self.all().create(**attributes)

    def first_or_create(self, **attributes):
        return self.all().first_or_create(**attributes)

    def __len__(self):
        return len(self._collection())

    def __iter__(self):
        return iter(self._collection())

    def __getitem__(self, index):
        return self._collection()[index]

    def __setitem__(self, index, value):
        self._collection()[index] = value

    def __delitem__(self, index):
        del self._collection()[index]

    def insert(self, index, value):
        self._collection().insert(index, value)

    def __eq__(self, other):
        return self._collection() == other

    def __repr__(self):
        return repr(self._collection())


def _declare(name, kind, class_name, foreign_key, dependent, inverse_of, optional):
    if not isinstance(name, str) or not name.isidentifier() or name.startswith("_"):
        raise ProgrammerError("Association names must be public Python identifiers.")
    if class_name is not None and (not isinstance(class_name, str) or not class_name):
        raise ProgrammerError("Association targets must be nonempty strings.")
    if foreign_key is not None and (
        not isinstance(foreign_key, str) or not foreign_key
    ):
        raise ProgrammerError("Association foreign keys must be nonempty strings.")
    if dependent not in (None, "destroy"):
        raise ProgrammerError("Association dependent must be 'destroy' or None.")

    def bind(cls):
        target = class_name or inflector.camelize(
            inflector.singularize(name) if kind == "has_many" else name
        )
        key = foreign_key or inflector.foreign_key(
            target if kind == "belongs_to" else cls.__name__
        )
        definition = model_for(cls)
        if name in definition.associations:
            raise ProgrammerError(f"Duplicate association {cls.__name__}.{name}.")
        if any(name in vars(base) for base in cls.__mro__):
            raise ProgrammerError(
                f"Association {cls.__name__}.{name} conflicts with a model attribute."
            )
        definition.associations[name] = AssociationDefinition(
            name, kind, target, key, dependent, inverse_of, optional
        )
        if kind == "belongs_to" and not optional:
            definition.validators.append(
                lambda *, instance: _validate_target(instance, name, target, key)
            )

    return bind


@declaration
def belongs_to(
    name, class_name=None, foreign_key=None, *, inverse_of=None, optional=False
):
    return _declare(
        name, "belongs_to", class_name, foreign_key, None, inverse_of, optional
    )


@declaration
def has_many(
    name, class_name=None, foreign_key=None, dependent=None, *, inverse_of=None
):
    return _declare(
        name, "has_many", class_name, foreign_key, dependent, inverse_of, True
    )


@declaration
def has_one(
    name, class_name=None, foreign_key=None, dependent=None, *, inverse_of=None
):
    return _declare(
        name, "has_one", class_name, foreign_key, dependent, inverse_of, True
    )


def _validate_target(instance, name, target_name, key):
    state = inspect(instance)
    attribute = state.attrs[name]
    if attribute.history.has_changes() or instance.is_new_record():
        value = attribute.loaded_value
        if value is not NO_VALUE and value is not None:
            return []
        if attribute.history.has_changes():
            return [(name, f"{name} must exist")]
    identity = getattr(instance, key)
    target = instance._flaskteroids_model_root._flaskteroids_model_catalog[target_name]
    if identity is not None and session.get(target, identity) is not None:
        return []
    return [(name, f"{name} must exist")]


def relationship_properties(cls, catalog, table_for):
    result = {}
    source = table_for(cls)
    for name, definition in model_for(cls).associations.items():
        if name in source.columns:
            raise ProgrammerError(
                f"Association {cls.__name__}.{name} conflicts with a snapshot column."
            )
        target = catalog[definition.target]
        target_table = table_for(target)
        fk_table, pk_table = (
            (source, target_table)
            if definition.kind == "belongs_to"
            else (target_table, source)
        )
        if definition.foreign_key not in fk_table.columns:
            raise ProgrammerError(
                f"Association {cls.__name__}.{name} needs {fk_table.name}.{definition.foreign_key}."
            )
        if len(pk_table.primary_key) != 1:
            raise ProgrammerError(
                "Association helpers require a single-column primary key; use relationship() for composite keys."
            )
        key = fk_table.c[definition.foreign_key]
        primary_key = next(iter(pk_table.primary_key))
        inverses = [
            other.name
            for other in model_for(target).associations.values()
            if other.target == cls.__name__
            and other.foreign_key == definition.foreign_key
            and (other.kind == "belongs_to") != (definition.kind == "belongs_to")
        ]
        inverse = definition.inverse_of
        if inverse is not None:
            if inverse not in inverses:
                raise ProgrammerError(
                    f"Invalid inverse {target.__name__}.{inverse} for {cls.__name__}.{name}."
                )
        elif len(inverses) > 1:
            raise ProgrammerError(
                f"Ambiguous inverse for {cls.__name__}.{name}; specify inverse_of."
            )
        else:
            inverse = next(iter(inverses), None)
        result[name] = relationship(
            target,
            primaryjoin=primary_key == key,
            foreign_keys=[key],
            back_populates=inverse,
            uselist=definition.kind == "has_many",
            remote_side=[primary_key]
            if cls is target and definition.kind == "belongs_to"
            else None,
        )
    return result


def destroy_dependents(instance):
    for definition in model_for(type(instance)).associations.values():
        if definition.dependent != "destroy":
            continue
        value = getattr(instance, definition.name)
        for record in (
            list(value)
            if definition.kind == "has_many"
            else ([value] if value is not None else [])
        ):
            if not record.destroy():
                return False
    return True
