"""Class-body declarations translated to native relationships before mapping."""

from sqlalchemy import false, inspect
from sqlalchemy.orm import relationship, with_parent
from sqlalchemy.orm.attributes import (
    INCLUDE_PENDING_MUTATIONS,
    NO_VALUE,
    PASSIVE_NO_INITIALIZE,
    get_history,
)

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
        if model_for(type(self.owner)).associations[self.name].autosave is True:
            # Keep explicitly autosaved targets in native association storage.
            object.__getattribute__(self.owner, self.name)
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


class AssociationCollection:
    """Association operations and query scopes over native mapped records."""

    def __init__(self, owner, name):
        self.owner = owner
        self.name = name

    def _collection(self):
        # Bypass the application-facing getter, not SQLAlchemy instrumentation.
        return object.__getattribute__(self.owner, self.name)

    def _loaded_collection(self):
        return inspect(self.owner).attrs[self.name].loaded_value

    def _pending_records(self):
        return get_history(
            self.owner,
            self.name,
            passive=PASSIVE_NO_INITIALIZE | INCLUDE_PENDING_MUTATIONS,
        ).added

    def _pending_count(self):
        return sum(record.is_new_record() for record in self._pending_records())

    def _records_for_finder(self):
        records = self._loaded_collection()
        if records is not NO_VALUE:
            return records
        if self.owner.is_new_record() or self._pending_records():
            return self._collection()
        return NO_VALUE

    def is_loaded(self) -> bool:
        return self._loaded_collection() is not NO_VALUE

    def all(self) -> ModelQuery:
        return AssociationQuery(self.owner, self.name)

    def where(self, *expressions, **filters) -> ModelQuery:
        return self.all().where(*expressions, **filters)

    def order(self, *expressions, **directions: str) -> ModelQuery:
        return self.all().order(*expressions, **directions)

    def limit(self, value: int | None) -> ModelQuery:
        return self.all().limit(value)

    def offset(self, value: int | None) -> ModelQuery:
        return self.all().offset(value)

    def includes(self, *paths: str) -> ModelQuery:
        return self.all().includes(*paths)

    def options(self, *options) -> ModelQuery:
        return self.all().options(*options)

    def with_all_rich_text(self) -> ModelQuery:
        return self.all().with_all_rich_text()

    def with_rich_text_embeds(self, *names) -> ModelQuery:
        return self.all().with_rich_text_embeds(*names)

    def to_sql(self) -> str:
        return self.all().to_sql()

    def count(self) -> int:
        return 0 if self.owner.is_new_record() else self.all().count()

    def size(self) -> int:
        records = self._loaded_collection()
        if records is not NO_VALUE:
            return len(records)
        if self.owner.is_new_record():
            return len(self._collection())
        return self.count() + self._pending_count()

    def first(self):
        records = self._records_for_finder()
        if records is not NO_VALUE:
            return records[0] if records else None
        return self.all().first()

    def last(self):
        records = self._records_for_finder()
        if records is not NO_VALUE:
            return records[-1] if records else None
        return self.all().last()

    def find(self, id):
        return self.all().find(id)

    def find_by(self, **filters):
        return self.all().find_by(**filters)

    def new(self, **attributes):
        return self.all().new(**attributes)

    def create(self, **attributes):
        return self.all().create(**attributes)

    def first_or_create(self, **attributes):
        record = self.first()
        return record if record is not None else self.create(**attributes)

    def __len__(self):
        return len(self._collection())

    def __iter__(self):
        return iter(self._collection())

    def __contains__(self, record):
        return record in self._collection()

    def __reversed__(self):
        return reversed(self._collection())

    def __iadd__(self, records):
        self.extend(records)
        return self

    def __getitem__(self, index):
        return self._collection()[index]

    def __setitem__(self, index, value):
        self._collection()[index] = value

    def __delitem__(self, index):
        del self._collection()[index]

    def insert(self, index, value):
        self._collection().insert(index, value)

    def append(self, record):
        self.insert(len(self), record)

    def extend(self, records):
        self._collection().extend(records)

    def remove(self, record):
        self._collection().remove(record)

    def clear(self):
        self._collection().clear()

    def pop(self, index=-1):
        record = self[index]
        del self[index]
        return record

    def index(self, record, start=0, stop=None):
        records = self._collection()
        return records.index(record, start, len(records) if stop is None else stop)

    def reverse(self):
        self._collection().reverse()

    def __eq__(self, other):
        return self._collection() == other

    def __repr__(self):
        return repr(self._collection())


def _declare(
    name,
    kind,
    class_name,
    foreign_key,
    dependent,
    inverse_of,
    optional,
    autosave,
    through=None,
    source=None,
):
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

    if autosave is not None and type(autosave) is not bool:
        raise ProgrammerError("Association autosave must be True, False, or None.")

    for option, value in (("through", through), ("source", source)):
        if value is not None and (
            not isinstance(value, str)
            or not value.isidentifier()
            or value.startswith("_")
        ):
            raise ProgrammerError(f"Association {option} must be a public identifier.")
    if source is not None and through is None:
        raise ProgrammerError("source requires a through association.")
    if through is not None and any(
        value is not None
        for value in (class_name, foreign_key, dependent, inverse_of, autosave)
    ):
        raise ProgrammerError(
            "Configure class_name, foreign_key, dependent, inverse_of, and autosave "
            "on the join associations, not the through collection."
        )

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
            name,
            kind,
            target,
            key,
            dependent,
            inverse_of,
            optional,
            autosave,
            through,
            source,
        )
        if kind == "belongs_to" and not optional:
            definition.validators.append(
                lambda *, instance: _validate_target(instance, name, target, key)
            )

    return bind


@declaration
def belongs_to(
    name,
    class_name=None,
    foreign_key=None,
    *,
    inverse_of=None,
    optional=False,
    autosave=None,
):
    return _declare(
        name,
        "belongs_to",
        class_name,
        foreign_key,
        None,
        inverse_of,
        optional,
        autosave,
    )


@declaration
def has_many(
    name,
    class_name=None,
    foreign_key=None,
    dependent=None,
    *,
    inverse_of=None,
    autosave=None,
    through=None,
    source=None,
):
    return _declare(
        name,
        "has_many",
        class_name,
        foreign_key,
        dependent,
        inverse_of,
        True,
        autosave,
        through,
        source,
    )


@declaration
def has_one(
    name,
    class_name=None,
    foreign_key=None,
    dependent=None,
    *,
    inverse_of=None,
    autosave=None,
):
    return _declare(
        name, "has_one", class_name, foreign_key, dependent, inverse_of, True, autosave
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
    definition = model_for(cls)
    attribute_names = (
        set(source.columns.keys())
        | definition.associations.keys()
        | definition.virtual_fields.keys()
        | definition.attachments.keys()
        | definition.rich_texts.keys()
    )
    for name in definition.nested_attributes:
        if f"{name}_attributes" in attribute_names:
            raise ProgrammerError(
                f"Nested writer {name}_attributes conflicts with a model attribute."
            )
    for name, definition in model_for(cls).associations.items():
        if name in source.columns:
            raise ProgrammerError(
                f"Association {cls.__name__}.{name} conflicts with a snapshot column."
            )
        if definition.through is not None:
            continue
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
            if other.through is None
            and other.target == cls.__name__
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
            cascade="merge" if definition.autosave is False else "save-update, merge",
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
