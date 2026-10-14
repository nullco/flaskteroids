from __future__ import annotations

from datetime import UTC, datetime
from typing import Self

from sqlalchemy import inspect

from flaskteroids import fields
from flaskteroids._models.associations import (
    Relation,
    _get_association,
    belongs_to,
    has_many,
)
from flaskteroids._models.authentication import (
    PasswordAuthenticator,
    has_secure_password,
)
from flaskteroids._models.query import ModelQuery
from flaskteroids._models.records import _base

# Configuration types remain directly importable, including those outside __all__.
from flaskteroids._models.validation import (  # noqa: F401
    ComparisonConfig,
    Error,
    Errors,
    LengthConfig,
    PresenceConfig,
    validates,
)
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
from flaskteroids.db import session
from flaskteroids.declarations import model_for
from flaskteroids.exceptions import RecordNotFoundException
from flaskteroids.rules import bind_rules

__all__ = [
    "Error",
    "Errors",
    "LengthConfig",
    "Model",
    "ModelMeta",
    "ModelQuery",
    "PasswordAuthenticator",
    "RecordNotFoundException",
    "Relation",
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
    "has_many",
    "has_many_attached",
    "has_one_attached",
    "has_secure_password",
    "init",
    "validates",
]


def init(cls):
    bind_rules(cls)
    return cls


def _declared_attribute(model_cls, name):
    # Dynamic class lookup invokes ModelMeta and may require a database mapping.
    for owner in model_cls.__mro__:
        if name in vars(owner):
            return owner, vars(owner)[name]
    return None, None


def _reserved_attribute(name):
    return name.startswith("_flaskteroids_") or any(
        name in vars(owner) for owner in (Model, PasswordAuthenticator, object)
    )


def _check_assignment_kwargs(model_cls, kwargs):
    for name in kwargs:
        if name in Model._fields or _reserved_attribute(name):
            raise AttributeError(
                f"{model_cls.__name__}.{name} is reserved framework state or API."
            )


class ModelMeta(type):
    def __getattr__(cls, name):
        base = _base(cls)
        return getattr(base, name)


class Model(metaclass=ModelMeta):
    _fields = (
        "_changes",
        "_virtual_fields",
        "_base_instance",
        "_errors",
        "_attachment_changes",
        "_attachment_cache",
    )

    def _initialize(self):
        self._attachment_changes = {}
        self._attachment_cache = {}
        self._virtual_fields = {}
        self._changes = {}
        self._base_instance = _base(self.__class__)()
        self._errors = Errors()

    def __init__(self, **kwargs):
        _check_assignment_kwargs(self.__class__, kwargs)
        self._initialize()
        for k, v in kwargs.items():
            setattr(self, k, v)
        run_callbacks(self, "initialize", None, lambda: None)

    @property
    def errors(self):
        return self._errors

    @property
    def column_names(self):
        return list(self._base_instance.__table__.columns.keys())

    def __getattr__(self, name):
        vfd = model_for(self.__class__).virtual_fields
        if (
            name in vfd
            and vfd[name].get("read_only", False)
            and (name not in self._virtual_fields or not vfd[name].get("cache", True))
        ):
            set_fn = vfd[name].get("set_fn")
            if set_fn:
                set_fn(self)
        if name in vfd:
            return self._virtual_fields.get(name)
        if name in self._changes:
            return self._changes[name]
        return getattr(self._base_instance, name)

    def __setattr__(self, name, value):
        if name in Model._fields:
            object.__setattr__(self, name, value)
            return
        if attached_storage.assign(self, name, value):
            return
        definition = model_for(self.__class__)
        field_name = f"{self.__class__.__name__}.{name}"
        if name in definition.virtual_fields:
            virtual_field = definition.virtual_fields[name]
            if virtual_field.get("read_only", False):
                raise AttributeError(f"{field_name} is a read-only virtual field.")
            self._virtual_fields[name] = value
            set_fn = virtual_field.get("set_fn")
            if set_fn:
                set_fn(self)
            return
        if name in self._base_instance.__table__.columns:
            column = self._base_instance.__table__.columns[name]
            converted = fields.from_column_type(column.type).as_primitive(value)
            self._changes[name] = converted
            return
        if name in definition.associations:
            if definition.associations[name].kind == "has_many":
                raise AttributeError(
                    f"{field_name} cannot be replaced; use Relation iteration and create()."
                )
            association = _get_association(self.__class__, name=name)
            if value is not None and not isinstance(value, association.target):
                raise TypeError(
                    f"{field_name} expects {association.target.__name__} or None."
                )
            foreign_key = value.id if value is not None else None
            self._changes[association.foreign_key] = foreign_key
            self._changes[name] = value
            return
        if _reserved_attribute(name):
            raise AttributeError(f"{field_name} is reserved framework state or API.")
        owner, declared = _declared_attribute(self.__class__, name)
        if owner is not None:
            if hasattr(type(declared), "__set__"):
                if isinstance(declared, property) and declared.fset is None:
                    raise AttributeError(f"{field_name} is a read-only property.")
                object.__setattr__(self, name, value)
                return
            if callable(declared) or hasattr(type(declared), "__get__"):
                raise AttributeError(
                    f"{field_name} is a read-only method or descriptor."
                )
        if owner is not None or name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        raise AttributeError(
            f"Unknown attribute {field_name}; declare a class default or writable property "
            "for transient values, or use a private attribute."
        )

    def __json__(self):
        password_field = model_for(self.__class__).password_field or "password"
        sensitive = {
            f"{field}{suffix}"
            for field in {"password", password_field}
            for suffix in ("", "_confirmation", "_digest", "_reset_token")
        }
        return {
            name: self._changes[name]
            if name in self._changes
            else getattr(self._base_instance, name)
            for name in self.column_names
            if name not in sensitive
        }

    def _form_data(self):
        virtual_fields = model_for(self.__class__).virtual_fields
        writable_values = {
            name: value
            for name, value in self._virtual_fields.items()
            if not virtual_fields.get(name, {}).get("read_only", False)
        }
        stored_values = {
            name: getattr(self._base_instance, name) for name in self.column_names
        }
        column_changes = {
            name: value
            for name, value in self._changes.items()
            if name in stored_values
        }
        return writable_values | stored_values | column_changes

    @classmethod
    def new(cls, **kwargs) -> Self:
        instance = cls(**kwargs)
        return instance

    @classmethod
    def create(cls, **kwargs) -> Self:
        instance = cls.new(**kwargs)
        instance.save()
        return instance

    @classmethod
    def all(cls) -> ModelQuery[Self]:
        return ModelQuery(cls)

    @classmethod
    def count(cls) -> int:
        return ModelQuery(cls).count()

    @classmethod
    def first(cls) -> Self | None:
        return ModelQuery(cls).first()

    @classmethod
    def last(cls) -> Self | None:
        return ModelQuery(cls).last()

    @classmethod
    def includes(cls, *args: str) -> ModelQuery[Self]:
        return ModelQuery(cls).includes(*args)

    @classmethod
    def find(cls, id) -> Self:
        return ModelQuery(cls).find(id)

    @classmethod
    def find_by(cls, **kwargs) -> Self | None:
        return ModelQuery(cls).where(**kwargs).first()

    @classmethod
    def where(cls, *args, **kwargs) -> ModelQuery[Self]:
        return ModelQuery(cls).where(*args, **kwargs)

    @classmethod
    def order(cls, **kwargs: str) -> ModelQuery[Self]:
        return ModelQuery(cls).order(**kwargs)

    @classmethod
    def limit(cls, value: int | None) -> ModelQuery[Self]:
        return ModelQuery(cls).limit(value)

    @classmethod
    def offset(cls, value: int | None) -> ModelQuery[Self]:
        return ModelQuery(cls).offset(value)

    def update(self, **kwargs):
        _check_assignment_kwargs(self.__class__, kwargs)
        for field, value in kwargs.items():
            setattr(self, field, value)
        return self.save()

    def reload(self):
        session.refresh(self._base_instance)
        self._changes.clear()
        self._attachment_changes.clear()
        self._attachment_cache.clear()
        return self

    def _prepare_commit(self):
        attached_storage.cache_for_commit(self)

    def save(self, validate=True):
        operation = "create" if self.is_new_record() else "update"

        if validate:
            if run_callbacks(self, "validation", operation, self._validate) is _HALTED:
                return False
            if self._errors:
                return False

        if (
            run_callbacks(self, "save", operation, self._create_or_update, operation)
            is _HALTED
        ):
            return False

        queue_after_commit(self, operation, session)
        return True

    def _validate(self):
        validate_rules = model_for(self.__class__).validators
        self._errors = Errors()
        for vr in validate_rules:
            self._errors.extend(vr(instance=self))
        attached_storage.validate(self)

    def _create_or_update(self, operation):
        if operation == "create":
            result = run_callbacks(self, "create", None, self._create_record)
        else:
            result = run_callbacks(self, "update", None, self._update_record)
        if result is not _HALTED:
            attached_storage.persist(self)
        return result

    def _apply_changes(self):
        associations = model_for(self.__class__).associations
        for field, value in self._changes.items():
            if field in associations and value is not None:
                value = value._base_instance
            setattr(self._base_instance, field, value)
        self._changes.clear()

    def _create_record(self):
        self._apply_changes()
        now = datetime.now(UTC)
        self._base_instance.created_at = now
        self._base_instance.updated_at = now
        session.add(self._base_instance)
        session.flush()

    def _update_record(self):
        self._apply_changes()
        self._base_instance.updated_at = datetime.now(UTC)
        session.flush()

    def is_persisted(self):
        return inspect(self._base_instance).persistent

    def is_new_record(self):
        return not self.is_persisted()

    def destroy(self):
        if run_callbacks(self, "destroy", None, self._destroy_record) is _HALTED:
            return False
        queue_after_commit(self, "destroy", session)
        return True

    def _destroy_record(self):
        attached_storage.destroy(self)
        session.delete(self._base_instance)
        session.flush()

    def __repr__(self) -> str:
        values = {c: getattr(self._base_instance, c) for c in self.column_names}
        return f"<{self.__class__.__name__}:{hex(id(self))} {values}>"
