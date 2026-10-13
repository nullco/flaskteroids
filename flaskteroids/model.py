import hmac
import logging
from datetime import datetime, timezone
from functools import partial
from typing import Any, NotRequired, TypedDict

from flask import current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import relationship, selectinload
from werkzeug.security import check_password_hash, generate_password_hash

import flaskteroids.registry as registry
from flaskteroids import fields
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
from flaskteroids.exceptions import ProgrammerError, RecordNotFoundException
from flaskteroids.inflector import inflector
from flaskteroids.rules import bind_rules

__all__ = [
    'Model',
    'ModelMeta',
    'ModelQuery',
    'init',
    'RecordNotFoundException',
    'Error',
    'Errors',
    'PasswordAuthenticator',
    'has_secure_password',
    'belongs_to',
    'has_many',
    'has_one_attached',
    'has_many_attached',
    'validates',
    'Relation',
    'before_validation',
    'after_validation',
    'before_save',
    'around_save',
    'after_save',
    'before_create',
    'around_create',
    'after_create',
    'before_update',
    'around_update',
    'after_update',
    'before_destroy',
    'around_destroy',
    'after_destroy',
    'after_commit',
    'after_rollback',
    'after_initialize',
    'after_find',
]

_logger = logging.getLogger(__name__)


def init(cls):
    bind_rules(cls)
    return cls


class Error:
    def __init__(self, args) -> None:
        self._args = args

    def full_message(self):
        return self._args[-1]

    def __repr__(self):
        return f'<ModelError:{hex(id(self))} {{args={self._args}}}>'


class Errors:

    def __init__(self) -> None:
        self._errors = []

    def append(self, error):
        self._errors.append(Error(error))

    def extend(self, errors):
        self._errors.extend([Error(e) for e in errors])

    def full_messages(self):
        return [e.full_message() for e in self._errors]

    @property
    def count(self):
        return len(self._errors)

    def __bool__(self):
        return bool(self._errors)

    def __repr__(self):
        return repr([e for e in self._errors])

    def __len__(self):
        return len(self._errors)


def _register_association(name, rel, cls, related_cls, fk_name):
    ns = registry.get(cls)
    key = (related_cls.__name__, fk_name)
    if 'associations' not in ns:
        ns['associations'] = {}
    ns['associations'][key] = {'rel': rel, 'name': name, 'class': related_cls, 'fk_name': fk_name}


def _link_associations(name, rel, cls, related_cls, fk_name):
    ns = registry.get(related_cls)
    key = (cls.__name__, fk_name)
    if key in ns.get('associations', {}):
        rel.back_populates = ns['associations'][key]['name']
        bp = ns['associations'][key]['rel']
        bp.back_populates = name


def _password_reset_serializer(model_cls, pwname):
    salt = f'pwres:{model_cls.__module__}.{model_cls.__qualname__}:{pwname}'
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt=salt)


def _password_reset_fingerprint(serializer, password_digest):
    return hmac.new(serializer.secret_key, f'pwres:{password_digest}'.encode(), 'sha256').hexdigest()


class PasswordAuthenticator:
    @classmethod
    def authenticate_by(cls, **kwargs):
        ns = registry.get(cls)
        pwname = ns.get('password_field')
        if not pwname:
            return
        password = kwargs.pop(pwname)
        entry = cls.find_by(**kwargs)
        if not entry:
            check_password_hash('a', 'b')  # To protect against timing attacks
            return None
        if not entry.authenticate(password):
            return None
        return entry

    @classmethod
    def find_by_password_reset_token(cls, token):
        pwname = registry.get(cls).get('password_field')
        if not pwname:
            raise ProgrammerError('Password reset tokens require has_secure_password().')
        serializer = _password_reset_serializer(cls, pwname)
        payload = serializer.loads(token, max_age=900)
        if (
            not isinstance(payload, dict)
            or type(payload.get('id')) is not int
            or not isinstance(payload.get('fingerprint'), str)
            or not payload['fingerprint'].isascii()
        ):
            raise BadSignature('Invalid password reset token.')
        entry = cls.find(payload['id'])
        fingerprint = _password_reset_fingerprint(serializer, getattr(entry, f'{pwname}_digest'))
        if not hmac.compare_digest(payload['fingerprint'], fingerprint):
            raise BadSignature('Password reset token has been invalidated.')
        return entry

    def authenticate(self, password):
        ns = registry.get(self.__class__)
        pwname = ns.get('password_field')
        if not pwname:
            return False
        password_digest = getattr(self, f'{pwname}_digest')
        return check_password_hash(password_digest, password)


def has_secure_password(pwname='password'):
    def bind(cls):

        ns = registry.get(cls)
        ns['password_field'] = pwname
        virtual_fields = ns.setdefault('virtual_fields', {})

        def _set_password_digest(self):
            value = getattr(self, f'{pwname}')
            setattr(self, f'{pwname}_digest', generate_password_hash(value))

        virtual_fields[pwname] = {
            'set_fn': _set_password_digest
        }

        def _set_password_reset_token(self):
            serializer = _password_reset_serializer(self.__class__, pwname)
            fingerprint = _password_reset_fingerprint(serializer, getattr(self, f'{pwname}_digest'))
            token = serializer.dumps({'id': self.id, 'fingerprint': fingerprint})
            self._virtual_fields[f'{pwname}_reset_token'] = token

        virtual_fields[f'{pwname}_reset_token'] = {
            'read_only': True,
            'cache': False,
            'set_fn': _set_password_reset_token
        }

        validates(pwname, length={'minimum': 1, 'maximum': 72})(cls)
        validates(pwname, confirmation=True)(cls)
    return bind


def belongs_to(name: str, class_name: str | None = None, foreign_key: str | None = None):
    def bind(cls):
        ns = registry.get(Model)
        models = ns['models']
        related_cls_name = class_name or inflector.camelize(name)
        related_cls = models.get(related_cls_name)
        if not related_cls:
            raise ProgrammerError(f'{related_cls_name} model not found')
        try:
            related_base = _base(related_cls)
            base = _base(cls)
        except Exception:
            return  # TODO: Handle better this
        fk_name = foreign_key or inflector.foreign_key(related_cls.__name__)
        fk = getattr(base, fk_name)
        rel = relationship(related_base, primaryjoin=related_base.id == fk)
        setattr(base, name, rel)
        _register_association(name, rel, cls, related_cls, fk_name)
        _link_associations(name, rel, cls, related_cls, fk_name)

        def rel_wrapper(self):
            related_base_instance = getattr(self._base_instance, name)
            if not related_base_instance:
                return None
            return _build(related_cls, related_base_instance)

        setattr(cls, name, property(rel_wrapper))

        registry.get(cls).setdefault('validates', []).append(
            partial(_validate_fk, field=fk_name)
        )
    return bind


class Relation:
    def __init__(self, instance, related_cls, name) -> None:
        self._instance = instance
        self._related_cls = related_cls
        self._name = name

    def _entries(self):
        return getattr(self._instance._base_instance, self._name)

    def __len__(self):
        return len(self._entries())

    def __iter__(self):
        for v in self._entries():
            yield _build(self._related_cls, v)

    def __repr__(self) -> str:
        return repr([v for v in self])

    def create(self, **kwargs):
        related_instance = self._related_cls.new(**kwargs)
        self._entries().append(related_instance._base_instance)
        self._instance.save()
        return related_instance


def has_many(name: str, class_name: str | None = None, foreign_key: str | None = None, dependent: str | None = None):
    def bind(cls):
        ns = registry.get(Model)
        models = ns['models']
        related_cls_name = class_name or inflector.camelize(inflector.singularize(name))
        related_cls = models.get(related_cls_name)
        if not related_cls:
            raise ProgrammerError(f'{related_cls_name} model not found')
        try:
            related_base = _base(related_cls)
            base = _base(cls)
        except Exception:
            return  # TODO: Handle better this
        fk_name = foreign_key or inflector.foreign_key(cls.__name__)
        fk = getattr(related_base, fk_name)
        match dependent:
            case 'destroy':
                cascade = 'all, delete-orphan'
            case _:
                cascade = 'save-update, merge'
        rel = relationship(related_base, primaryjoin=base.id == fk, cascade=cascade)
        setattr(base, name, rel)
        _register_association(name, rel, cls, related_cls, fk_name)
        _link_associations(name, rel, cls, related_cls, fk_name)

        def rel_wrapper(self):
            return Relation(self, related_cls, name)

        setattr(cls, name, property(rel_wrapper))
    return bind


class PresenceConfig(TypedDict):
    message: NotRequired[str]


class LenghtConfig(TypedDict):
    minimum: NotRequired[int]
    maximum: NotRequired[int]


class ComparisonConfig(TypedDict):
    greater_than: NotRequired[Any]
    less_than: NotRequired[Any]
    less_than_or_equal_to: NotRequired[Any]
    greater_than_or_equal_to: NotRequired[Any]
    equal_to: NotRequired[Any]
    other_than: NotRequired[Any]


def validates(field, *,
              presence: None | PresenceConfig | bool = None,
              length: None | LenghtConfig = None,
              confirmation: None | bool = None,
              comparison: None | ComparisonConfig = None):
    options = {
        'presence': {'config': presence, 'validator': _validate_presence},
        'length': {'config': length, 'validator': _validate_length},
        'confirmation': {'config': confirmation, 'validator': _validate_confirmation},
        'comparison': {'config': comparison, 'validator': _validate_comparison},
    }
    options = {k: v for k, v in options.items() if v['config'] is not None}

    def bind(model_cls):
        ns = registry.get(model_cls)
        for value in options.values():
            ns.setdefault('validates', []).append(
                partial(value['validator'], field=field, config=value['config'])
            )
        if 'confirmation' in options:
            ns.setdefault('virtual_fields', {})[f'{field}_confirmation'] = {}
    return bind


def _validate_presence(*, instance, field, config):
    if not config:
        return []
    if isinstance(config, bool):
        config = {'message': f'Field {field} is blank'}

    errors = []
    value = getattr(instance, field)
    if value is None or value == '':
        errors.append((f'{field}.presence', config['message']))
    return errors


def _validate_length(*, instance, field, config: LenghtConfig | None):
    if not config:
        return []
    errors = []
    value = getattr(instance, field)

    if value is not None:
        minimum = config.get('minimum')
        maximum = config.get('maximum')
        if minimum is not None and len(value) < minimum:
            errors.append((f'{field}.length', f"Field {field} is lower than {minimum}"))
        if maximum is not None and len(value) > maximum:
            errors.append((f'{field}.length', f"Field {field} is higher than {maximum}"))
    return errors


def _validate_confirmation(*, instance, field, config: None | bool):
    if not config:
        return []
    errors = []
    value = getattr(instance, field)
    if value is not None:
        confirmation_field = f'{field}_confirmation'
        if confirmation_field in instance._virtual_fields:
            confirmation_value = instance._virtual_fields.get(confirmation_field)
            if confirmation_value != value:
                errors.append((f'{field}.confirmation', f"Field {field} values do not match"))
    return errors


def _resolve_comparison_value(instance, compare_value):
    if callable(compare_value):
        return compare_value()
    if isinstance(compare_value, str):
        return getattr(instance, compare_value, None)
    return compare_value


def _validate_comparison(*, instance, field, config):
    if not config:
        return []
    errors = []
    value = getattr(instance, field)
    if value is None:
        return errors

    comparisons = {
        'greater_than': (lambda a, b: a > b, 'must be greater than'),
        'less_than': (lambda a, b: a < b, 'must be less than'),
        'greater_than_or_equal_to': (lambda a, b: a >= b, 'must be greater than or equal to'),
        'less_than_or_equal_to': (lambda a, b: a <= b, 'must be less than or equal to'),
        'equal_to': (lambda a, b: a == b, 'must be equal to'),
        'other_than': (lambda a, b: a != b, 'must be other than'),
    }

    for comparator, raw_compare_value in config.items():
        if comparator not in comparisons:
            continue

        compare_value = _resolve_comparison_value(instance, raw_compare_value)
        if compare_value is None:
            continue

        check_fn, message = comparisons[comparator]
        try:
            if not check_fn(value, compare_value):
                _logger.debug(f"Comparison failed: instance={instance!r}, field={field}, value={value}, comparator={comparator}, compare_value={compare_value}")
                errors.append((f'{field}.comparison', f"Field {field} {message} {compare_value}"))
        except TypeError:
            _logger.debug(f"Comparison type error: instance={instance!r}, field={field}, value={value}, comparator={comparator}, compare_value={compare_value}")
            errors.append((f'{field}.comparison', f"Field {field} cannot be compared with {compare_value}"))

    return errors


def _validate_fk(*, instance, field, config=True):
    if not config:
        return []
    association = _get_association(instance.__class__, name=field)
    if not association:
        return []
    value = getattr(instance, field)
    if not value:
        return [(field, f'{association["name"]} must exist')]
    related_cls = association['class']
    try:
        related_cls.find(value)
        return []
    except RecordNotFoundException:
        return [(field, f'{association["name"]} must exist')]


def _get_association(model_cls, *, name):
    ns = registry.get(model_cls)
    associations = ns.get('associations') or {}
    for cn, fk in associations.keys():
        if fk == name or associations[(cn, fk)]['name'] == name:
            return associations[(cn, fk)]


def _build(model_cls, base_instance):
    res = object.__new__(model_cls)
    res._initialize()
    res._base_instance = base_instance
    run_callbacks(res, 'initialize', None, lambda: None)
    run_callbacks(res, 'find', None, lambda: None)
    return res


def _base(model_cls):
    base = registry.get(model_cls).get('base_class')
    if not base:
        raise ProgrammerError(
            f'Base class not found for model {model_cls.__name__}.\n'
            'Make sure there is a table in the database backing it up.',
            'Did you create/run database migrations?'
        )
    return base


class ModelQuery:
    def __init__(self, model_cls):
        self._model_cls = model_cls
        self._model_base = _base(model_cls)
        self._query = select(self._model_base)
        self._limit = None
        self._offset = None

    def find(self, id):
        found = self.where(id=id).first()
        if not found:
            raise RecordNotFoundException(f"{self._model_cls.__name__} record with id {id} was not found")
        return found

    def where(self, *args, **kwargs):
        if args:
            self._query = self._query.filter(*args)
        if kwargs:
            self._query = self._query.filter_by(**kwargs)
        return self

    def includes(self, *args):
        for rel in args:
            self._query = self._query.options(selectinload(getattr(self._model_base, rel)))
        return self

    def all(self):
        yield from self.__iter__()

    def first(self):
        res = session.execute(self._query).scalars().first()
        if not res:
            return None
        return _build(self._model_cls, res)

    def last(self):
        if self._limit is not None or self._offset is not None:
            records = session.execute(self._query).scalars().all()
            return _build(self._model_cls, records[-1]) if records else None
        primary_key = inspect(self._model_base).primary_key[0]
        query = self._query.order_by(primary_key.desc())
        res = session.execute(query).scalars().first()
        if not res:
            return None
        return _build(self._model_cls, res)

    def count(self):
        query = select(func.count()).select_from(self._query.subquery())
        return session.execute(query).scalar_one()

    def order(self, **kwargs):
        for k, v in kwargs.items():
            field = getattr(self._model_base, k)
            clause = field.desc() if v == 'desc' else field.asc()
            self._query = self._query.order_by(clause)
        return self

    def limit(self, value: int | None):
        self._query = self._query.limit(value)
        self._limit = value
        return self

    def offset(self, value: int | None):
        self._query = self._query.offset(value)
        self._offset = value
        return self

    def __iter__(self):
        res = session.execute(self._query).scalars()
        for r in res:
            yield _build(self._model_cls, r)

    def __repr__(self):
        return repr([r for r in self])

    def to_sql(self):
        return str(self._query.compile(compile_kwargs={"literal_binds": True}))

    def __json__(self):
        res = session.execute(self._query).scalars()
        return [_build(self._model_cls, r).__json__() for r in res]


class ModelMeta(type):
    def __getattr__(cls, name):
        base = _base(cls)
        return getattr(base, name)


class Model(metaclass=ModelMeta):

    _fields = ['_changes', '_virtual_fields', '_base_instance', '_errors', '_attachment_changes', '_attachment_cache']

    def _initialize(self):
        self._attachment_changes = {}
        self._attachment_cache = {}
        self._virtual_fields = {}
        self._changes = {}
        self._base_instance = _base(self.__class__)()
        self._errors = Errors()

    def __init__(self, **kwargs):
        self._initialize()
        for k, v in kwargs.items():
            setattr(self, k, v)
        run_callbacks(self, 'initialize', None, lambda: None)

    @property
    def errors(self):
        return self._errors

    @property
    def column_names(self):
        return list(self._base_instance.__table__.columns.keys())

    def __getattr__(self, name):
        ns = registry.get(self.__class__)
        vfd = ns.setdefault('virtual_fields', {})
        if name in vfd and vfd[name].get('read_only', False):
            if name not in self._virtual_fields or not vfd[name].get('cache', True):
                set_fn = vfd[name].get('set_fn')
                if set_fn:
                    set_fn(self)
        if name in self._virtual_fields:
            return self._virtual_fields[name]
        if name in self._changes:
            return self._changes[name]
        return getattr(self._base_instance, name)

    def __setattr__(self, name, value):
        if name in self._fields:
            super().__setattr__(name, value)
            return
        if attached_storage.assign(self, name, value):
            return
        ns = registry.get(self.__class__)
        vfd = ns.setdefault('virtual_fields', {})
        if name in vfd:
            if vfd[name].get('read_only', False):
                raise AttributeError('You are trying to update a read-only attribute')
            self._virtual_fields[name] = value
            set_fn = vfd[name].get('set_fn')
            if set_fn:
                set_fn(self)
        elif name in self._base_instance.__table__.columns:
            column = self._base_instance.__table__.columns[name]
            self._changes[name] = fields.from_column_type(column.type).as_primitive(value)
        else:
            association = _get_association(self.__class__, name=name)
            if association:
                self._changes[name] = value
                if association['fk_name'] != name:
                    self._changes[association['fk_name']] = value.id

    def __json__(self):
        password_field = registry.get(self.__class__).get('password_field', 'password')
        sensitive = {
            f'{field}{suffix}'
            for field in {'password', password_field}
            for suffix in ('', '_confirmation', '_digest', '_reset_token')
        }
        return {
            name: self._changes[name] if name in self._changes else getattr(self._base_instance, name)
            for name in self.column_names
            if name not in sensitive
        }

    def _form_data(self):
        virtual_fields = registry.get(self.__class__).get('virtual_fields', {})
        writable_values = {
            name: value for name, value in self._virtual_fields.items()
            if not virtual_fields.get(name, {}).get('read_only', False)
        }
        stored_values = {name: getattr(self._base_instance, name) for name in self.column_names}
        column_changes = {name: value for name, value in self._changes.items() if name in stored_values}
        return writable_values | stored_values | column_changes

    @classmethod
    def new(cls, **kwargs):
        instance = cls(**kwargs)
        return instance

    @classmethod
    def create(cls, **kwargs):
        instance = cls.new(**kwargs)
        instance.save()
        return instance

    @classmethod
    def all(cls):
        return ModelQuery(cls)

    @classmethod
    def count(cls):
        return ModelQuery(cls).count()

    @classmethod
    def first(cls):
        return ModelQuery(cls).first()

    @classmethod
    def last(cls):
        return ModelQuery(cls).last()

    @classmethod
    def includes(cls, *args):
        return ModelQuery(cls).includes(*args)

    @classmethod
    def find(cls, id):
        return ModelQuery(cls).find(id)

    @classmethod
    def find_by(cls, **kwargs):
        return ModelQuery(cls).where(**kwargs).first()

    @classmethod
    def where(cls, *args, **kwargs):
        return ModelQuery(cls).where(*args, **kwargs)

    @classmethod
    def order(cls, **kwargs):
        return ModelQuery(cls).order(**kwargs)

    @classmethod
    def limit(cls, value: int | None):
        return ModelQuery(cls).limit(value)

    @classmethod
    def offset(cls, value: int | None):
        return ModelQuery(cls).offset(value)

    def update(self, **kwargs):
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
        operation = 'create' if self.is_new_record() else 'update'

        if validate:
            if run_callbacks(self, 'validation', operation, self._validate) is _HALTED:
                return False
            if self._errors:
                return False

        if run_callbacks(self, 'save', operation, self._create_or_update, operation) is _HALTED:
            return False

        queue_after_commit(self, operation, session)
        return True

    def _validate(self):
        validate_rules = registry.get(self.__class__).get('validates') or []
        self._errors = Errors()
        for vr in validate_rules:
            self._errors.extend(vr(instance=self))
        attached_storage.validate(self)

    def _create_or_update(self, operation):
        if operation == 'create':
            result = run_callbacks(self, 'create', None, self._create_record)
        else:
            result = run_callbacks(self, 'update', None, self._update_record)
        if result is not _HALTED:
            attached_storage.persist(self)
        return result

    def _create_record(self):
        for field, value in self._changes.items():
            setattr(self._base_instance, field, value)
        self._changes.clear()
        now = datetime.now(timezone.utc)
        self._base_instance.created_at = now
        self._base_instance.updated_at = now
        session.add(self._base_instance)
        session.flush()

    def _update_record(self):
        for field, value in self._changes.items():
            setattr(self._base_instance, field, value)
        self._changes.clear()
        self._base_instance.updated_at = datetime.now(timezone.utc)
        session.flush()

    def is_persisted(self):
        return inspect(self._base_instance).persistent

    def is_new_record(self):
        return not self.is_persisted()

    def destroy(self):
        if run_callbacks(self, 'destroy', None, self._destroy_record) is _HALTED:
            return False
        queue_after_commit(self, 'destroy', session)
        return True

    def _destroy_record(self):
        attached_storage.destroy(self)
        session.delete(self._base_instance)
        session.flush()

    def __repr__(self) -> str:
        values = {c: getattr(self._base_instance, c) for c in self.column_names}
        return f'<{self.__class__.__name__}:{hex(id(self))} {values}>'
