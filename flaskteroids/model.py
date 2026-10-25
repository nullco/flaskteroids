from __future__ import annotations

from datetime import UTC, date, datetime, time
from inspect import getattr_static
from typing import Self

from flask import current_app
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import NO_VALUE

from flaskteroids._models.associations import (
    belongs_to,
    destroy_dependents,
    has_many,
    has_one,
)
from flaskteroids._models.attributes import schema_default
from flaskteroids._models.authentication import (
    PasswordAuthenticator,
    has_secure_password,
)
from flaskteroids._models.encryption import EncryptableRecord, encrypts
from flaskteroids._models.mapping import SchemaModel
from flaskteroids._models.query import ModelQuery
from flaskteroids._models.staging import StagedAttributes
from flaskteroids._models.validation import ComparisonConfig as ComparisonConfig
from flaskteroids._models.validation import Error, Errors, LengthConfig, validates
from flaskteroids._models.validation import PresenceConfig as PresenceConfig
from flaskteroids.attachments import attached as attached_storage
from flaskteroids.attachments import has_many_attached, has_one_attached
from flaskteroids.callbacks import (
    _HALTED,
    after_commit,
    after_create,
    after_destroy,
    after_find,
    after_initialize,
    after_rollback,
    after_save,
    after_update,
    after_validation,
    around_create,
    around_destroy,
    around_save,
    around_update,
    before_create,
    before_destroy,
    before_save,
    before_update,
    before_validation,
    queue_after_commit,
    run_callbacks,
)
from flaskteroids.db import session, transaction, transactional
from flaskteroids.declarations import model_for
from flaskteroids.exceptions import ProgrammerError, RecordNotFoundException
from flaskteroids.inflector import inflector
from flaskteroids.rich_text import attribute as rich_text_storage
from flaskteroids.rich_text import has_rich_text
from flaskteroids.rules import bind_rules

__all__ = [
    "Error",
    "Errors",
    "LengthConfig",
    "Model",
    "ModelQuery",
    "PasswordAuthenticator",
    "RecordNotFoundException",
    "after_commit",
    "after_create",
    "after_destroy",
    "after_find",
    "after_initialize",
    "after_rollback",
    "after_save",
    "after_update",
    "after_validation",
    "around_create",
    "around_destroy",
    "around_save",
    "around_update",
    "before_create",
    "before_destroy",
    "before_save",
    "before_update",
    "before_validation",
    "belongs_to",
    "encrypts",
    "has_many",
    "has_many_attached",
    "has_one",
    "has_one_attached",
    "has_rich_text",
    "has_secure_password",
    "init",
    "validates",
]


def init(cls):
    bind_rules(cls)
    return cls


class Model(EncryptableRecord, StagedAttributes, SchemaModel):
    __abstract__ = True
    _serialization_exclude = frozenset()
    strict_loading_by_default = False

    def _initialize(self):
        self._changes = {}
        self._saved_changes = {}
        self._raw_attributes = {}
        self._virtual_fields = {}
        self._errors = Errors()
        self._attachment_changes = {}
        self._attachment_cache = {}
        self._rich_text_changes = {}

    def __init__(self, **kwargs):
        init(type(self))
        self._initialize()
        for name in kwargs:
            self._check_assignment(name)
        for prop in inspect(type(self)).column_attrs:
            if prop.key not in kwargs:
                default = schema_default(prop.columns[0])
                if default is not NO_VALUE:
                    setattr(self, prop.key, default)
        for name, value in kwargs.items():
            setattr(self, name, value)
        run_callbacks(self, "initialize", None, lambda: None)

    def _check_assignment(self, name):
        field_name = f"{type(self).__name__}.{name}"
        if name.startswith("_"):
            raise AttributeError(f"{field_name} is reserved framework state or API.")
        definition = model_for(type(self))
        if name in definition.virtual_fields:
            if definition.virtual_fields[name].get("read_only"):
                raise AttributeError(f"{field_name} is read-only.")
            return
        if name in definition.attachments or name in definition.rich_texts:
            return
        mapper = inspect(type(self))
        if name in mapper.attrs:
            return
        if any(
            name in vars(owner) for owner in (*Model.__mro__, PasswordAuthenticator)
        ):
            raise AttributeError(f"{field_name} is reserved framework state or API.")
        missing = object()
        declared = getattr_static(type(self), name, missing)
        if declared is missing:
            raise AttributeError(f"Unknown attribute {field_name}.")
        if isinstance(declared, property) and declared.fset is None:
            raise AttributeError(f"{field_name} is read-only.")
        if callable(declared):
            raise AttributeError(f"{field_name} is a read-only method.")

    def __setattr__(self, name, value):
        if name.startswith("_"):
            if name.startswith("_flaskteroids_") or callable(
                getattr_static(type(self), name, None)
            ):
                raise AttributeError(
                    f"{type(self).__name__}.{name} is reserved framework API."
                )
            return super().__setattr__(name, value)
        self._check_assignment(name)
        if rich_text_storage.assign(self, name, value):
            return
        if attached_storage.assign(self, name, value):
            return
        definition = model_for(type(self)).virtual_fields.get(name)
        if definition is not None:
            self._virtual_fields[name] = value
            if setter := definition.get("set_fn"):
                setter(self)
            return
        super().__setattr__(name, value)

    def __getattr__(self, name):
        definition = model_for(type(self)).virtual_fields.get(name)
        if definition is None:
            raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")
        if definition.get("read_only") and (
            name not in self._virtual_fields or not definition.get("cache", True)
        ):
            if setter := definition.get("set_fn"):
                setter(self)
        return self._virtual_fields.get(name)

    @property
    def errors(self):
        return self._errors

    @property
    def column_names(self):
        return list(inspect(type(self)).column_attrs.keys())

    def _sensitive_attributes(self):
        password = model_for(type(self)).password_field or "password"
        return self._serialization_exclude | {
            f"{name}{suffix}"
            for name in {"password", password}
            for suffix in ("", "_confirmation", "_digest", "_reset_token")
        }

    def __json__(self):
        excluded = self._sensitive_attributes()
        return {
            name: getattr(self, name)
            for name in self.column_names
            if name not in excluded
        }

    def _form_data(self):
        excluded = self._sensitive_attributes()
        return {
            name: value
            for name, value in (
                self.attributes_before_type_cast | self._virtual_fields
            ).items()
            if name not in excluded
        }

    @classmethod
    def new(cls, **kwargs) -> Self:
        return cls(**kwargs)

    @classmethod
    def create(cls, **kwargs) -> Self:
        record = cls(**kwargs)
        record.save()
        return record

    @classmethod
    def all(cls) -> ModelQuery[Self]:
        return ModelQuery(cls)

    @classmethod
    def where(cls, *expressions, **filters) -> ModelQuery[Self]:
        return cls.all().where(*expressions, **filters)

    @classmethod
    def includes(cls, *paths: str) -> ModelQuery[Self]:
        return cls.all().includes(*paths)

    @classmethod
    def with_all_rich_text(cls) -> ModelQuery[Self]:
        return cls.all().with_all_rich_text()

    @classmethod
    def order(cls, *expressions, **directions) -> ModelQuery[Self]:
        return cls.all().order(*expressions, **directions)

    @classmethod
    def limit(cls, value: int | None) -> ModelQuery[Self]:
        return cls.all().limit(value)

    @classmethod
    def offset(cls, value: int | None) -> ModelQuery[Self]:
        return cls.all().offset(value)

    @classmethod
    def count(cls) -> int:
        return cls.all().count()

    @classmethod
    def first(cls) -> Self | None:
        return cls.all().first()

    @classmethod
    def last(cls) -> Self | None:
        return cls.all().last()

    @classmethod
    def find(cls, id) -> Self:
        return cls.all().find(id)

    @classmethod
    def find_by(cls, **filters) -> Self | None:
        return cls.where(**filters).first()

    def update(self, **kwargs):
        for name in kwargs:
            self._check_assignment(name)
        for name, value in kwargs.items():
            setattr(self, name, value)
        return self.save()

    def reload(self):
        current_app.extensions["flaskteroids.db"].require_model(type(self))
        session.refresh(self)
        self.discard_changes()
        self._saved_changes = {}
        self._errors = Errors()
        self._attachment_changes.clear()
        self._attachment_cache.clear()
        rich_text_storage.discard(self)
        return self

    def _prepare_commit(self):
        attached_storage.cache_for_commit(self)

    def is_valid(self):
        operation = "create" if self.is_new_record() else "update"
        return (
            run_callbacks(self, "validation", operation, self._validate) is not _HALTED
            and not self.errors
        )

    def _validate(self):
        self._errors = Errors()
        for validator in model_for(type(self)).validators:
            self._errors.extend(validator(instance=self))
        attached_storage.validate(self)
        rich_text_storage.validate(self)

    def _save_graph(self):
        records, seen = [], set()

        def visit(record):
            if id(record) in seen:
                return
            seen.add(id(record))
            records.append(record)
            state = inspect(record)
            for relationship in state.mapper.relationships:
                if not relationship.cascade.save_update:
                    continue
                value = state.attrs[relationship.key].loaded_value
                if value is NO_VALUE or value is None:
                    continue
                for related in value if relationship.uselist else [value]:
                    if isinstance(related, Model) and related.is_new_record():
                        visit(related)

        visit(self)
        return records

    @classmethod
    def transaction(cls, *, requires_new=False):
        return transaction(requires_new=requires_new)

    def save(self, validate=True):
        state = inspect(self)
        relationships = [
            (
                relationship,
                list(value) if relationship.uselist else value,
            )
            for relationship in state.mapper.relationships
            if state.attrs[relationship.key].history.has_changes()
            and (value := state.attrs[relationship.key].loaded_value) is not NO_VALUE
        ]
        result = self._save(validate=validate)
        if not result:
            # Rollback expires native relationship edits. Retain submitted input
            # and its inverse links so a rejected save can be corrected/retried.
            for relationship, value in relationships:
                if relationship.back_populates:
                    for related in value if relationship.uselist else [value]:
                        if related is not None:
                            object.__getattribute__(
                                related, relationship.back_populates
                            )
                setattr(self, relationship.key, [] if relationship.uselist else None)
                setattr(self, relationship.key, value)
        return result

    @transactional(rollback_on_false=True)
    def _save(self, validate=True):
        current_app.extensions["flaskteroids.db"].require_model(type(self))
        if inspect(self).was_deleted:
            raise ProgrammerError("A destroyed record cannot be saved.")
        operation = "create" if self.is_new_record() else "update"
        graph = self._save_graph()
        if validate:
            valid = [record.is_valid() for record in graph]
            if not all(valid):
                if valid[0]:
                    self.errors.append(("associations", "Associated record is invalid"))
                return False

        def persist():
            previous = {
                id(record): {
                    name: record.read_published_attribute(name)
                    for name in record.column_names
                }
                for record in graph
            }
            now = datetime.now(UTC)
            for record in graph:
                if (
                    record.is_new_record()
                    and "created_at" in record.column_names
                    and record.created_at is None
                ):
                    record.created_at = now
                if "updated_at" in record.column_names:
                    record.updated_at = now
                record.apply_changes()
            session.add(self)
            session.flush()
            for record in graph:
                rich_text_storage.persist(record)
            for record in graph:
                record._saved_changes = {
                    name: (old, new)
                    for name, old in previous[id(record)].items()
                    if old != (new := record.read_published_attribute(name))
                }
            attached_storage.persist(self)

        result = run_callbacks(
            self,
            "save",
            operation,
            lambda: run_callbacks(self, operation, None, persist),
        )
        if result is _HALTED:
            return False
        queue_after_commit(self, operation, session)
        return True

    def is_persisted(self):
        state = inspect(self)
        return (state.persistent or state.detached) and not state.was_deleted

    def is_new_record(self):
        state = inspect(self)
        return state.transient or state.pending

    def to_key(self):
        """Return primary key values, independent of persistence and URL slugs."""
        mapper = inspect(type(self))
        values = [
            getattr(self, mapper.get_property_by_column(column).key)
            for column in mapper.primary_key
        ]
        return values if all(value is not None for value in values) else None

    @classmethod
    def to_partial_path(cls):
        """The conventional record partial, without underscore or extension."""
        name = inflector.underscore(cls.__name__)
        return f"{inflector.pluralize(name)}/{name}"

    def to_param(self):
        """The public route identity; override intentionally for slug-based URLs."""
        return str(self.id) if self.is_persisted() else None

    @transactional(rollback_on_false=True)
    def destroy(self):
        current_app.extensions["flaskteroids.db"].require_model(type(self))
        if self.is_new_record():
            return False

        destroying = session.info.setdefault("flaskteroids.destroying", set())
        if self in destroying:
            return True

        def remove():
            if not destroy_dependents(self):
                return _HALTED
            attached_storage.destroy(self)
            rich_text_storage.destroy(self)
            session.delete(self)
            session.flush()

        destroying.add(self)
        try:
            if run_callbacks(self, "destroy", None, remove) is _HALTED:
                return False
            queue_after_commit(self, "destroy", session)
            return True
        finally:
            destroying.remove(self)

    def __repr__(self) -> str:
        excluded = self._sensitive_attributes() | self.encrypted_attributes()
        values = {
            name: self.read_published_attribute(name)
            for name in self.column_names
            if name not in excluded
        }
        for name, value in values.items():
            if isinstance(value, datetime):
                values[name] = value.isoformat(sep=" ")
            elif isinstance(value, (date, time)):
                values[name] = value.isoformat()
        return f"<{type(self).__name__}:{hex(id(self))} {values}>"


@event.listens_for(Model, "load", propagate=True)
def _loaded(record, context):
    init(type(record))
    record._initialize()
    run_callbacks(record, "find", None, lambda: None)
    run_callbacks(record, "initialize", None, lambda: None)


@event.listens_for(Session, "before_flush")
def _guard_staged_inserts(db_session, context, objects):
    for record in db_session.new:
        if isinstance(record, Model) and record.changes:
            raise ProgrammerError(
                f"New {type(record).__name__} has staged attributes. "
                "Call save() or apply_changes() before native flush."
            )
