import logging
from datetime import datetime, timezone
from functools import partial
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import select, inspect
from sqlalchemy.orm import relationship
from flaskteroids.db import session
from flaskteroids.exceptions import ProgrammerError
import flaskteroids.registry as registry
from flaskteroids.rules import bind_rules
from flaskteroids.str_utils import camel_to_snake, snake_to_camel, singularize

_logger = logging.getLogger(__name__)


def init(cls):
    bind_rules(cls)
    return cls


class RecordNotFoundException(Exception):
    pass


def _register_association(name, rel, cls, related_cls, fk_name):
    ns = registry.get(cls)
    key = (related_cls.__name__, fk_name)
    if 'associations' not in ns:
        ns['associations'] = {}
    ns['associations'][key] = {'rel': rel, 'name': name}


def _link_associations(name, rel, cls, related_cls, fk_name):
    ns = registry.get(related_cls)
    key = (cls.__name__, fk_name)
    if key in ns.get('associations', {}):
        rel.back_populates = ns['associations'][key]['name']
        bp = ns['associations'][key]['rel']
        bp.back_populates = name


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
        ns.setdefault('virtual_fields', {})[pwname] = {
            'map_to': f'{pwname}_digest',
            'map_fn': generate_password_hash
        }
        validates(pwname, length={'minimum': 1, 'maximum': 72})(cls)
        validates(pwname, confirmation=True)(cls)
    return bind


def belongs_to(name: str, class_name: str | None = None, foreign_key: str | None = None):
    def bind(cls):
        ns = registry.get(Model)
        models = ns['models']
        related_cls_name = class_name or snake_to_camel(name)
        related_cls = models.get(related_cls_name)
        if not related_cls:
            raise ProgrammerError(f'{related_cls_name} model not found')
        try:
            related_base = _base(related_cls)
            base = _base(cls)
        except Exception:
            return  # TODO: Handle better this
        fk_name = foreign_key or f'{camel_to_snake(related_cls.__name__)}_id'
        fk = getattr(base, fk_name)
        rel = relationship(related_base, primaryjoin=related_base.id == fk)
        setattr(base, name, rel)
        _register_association(name, rel, cls, related_cls, fk_name)
        _link_associations(name, rel, cls, related_cls, fk_name)

        def rel_wrapper(self):
            related_base_instance = getattr(self._base_instance, name)
            return _build(related_cls, related_base_instance)

        setattr(cls, name, property(rel_wrapper))
    return bind


def has_many(name: str, class_name: str | None = None, foreign_key: str | None = None):
    def bind(cls):
        ns = registry.get(Model)
        models = ns['models']
        related_cls_name = class_name or snake_to_camel(singularize(name))
        related_cls = models.get(related_cls_name)
        if not related_cls:
            raise ProgrammerError(f'{related_cls_name} model not found')
        try:
            related_base = _base(related_cls)
            base = _base(cls)
        except Exception:
            return  # TODO: Handle better this
        fk_name = foreign_key or f'{camel_to_snake(cls.__name__)}_id'
        fk = getattr(related_base, fk_name)
        rel = relationship(related_base, primaryjoin=base.id == fk)
        setattr(base, name, rel)
        _register_association(name, rel, cls, related_cls, fk_name)
        _link_associations(name, rel, cls, related_cls, fk_name)

        def rel_wrapper(self):
            class Many:
                def __init__(self, base_instance) -> None:
                    self._values = getattr(base_instance, name)

                def __iter__(self):
                    for v in self._values:
                        yield _build(related_cls, v)

                def __repr__(self) -> str:
                    return repr([v for v in self])

            return Many(self._base_instance)

        setattr(cls, name, property(rel_wrapper))
    return bind


def validates(field, *, presence=False, length=None, confirmation=False):
    def bind(model_cls):
        ns = registry.get(model_cls)
        ns.setdefault('validates', []).append(
            partial(
                _validates,
                field=field, presence=presence, length=length, confirmation=confirmation
            )
        )
        if confirmation:
            ns.setdefault('virtual_fields', {})[f'{field}_confirmation'] = {}
    return bind


def _validates(*, instance, field, presence, length, confirmation):
    errors = []
    if hasattr(instance, field):
        value = getattr(instance, field)
    elif field in instance._virtual_fields:
        value = instance._virtual_fields[field]
    else:
        return

    if presence and value is None:
        errors.append((f'{field}.presence', f"Field {field} is missing"))
        return errors
    elif value is not None:
        if length:
            minimum = length.get('minimum')
            maximum = length.get('maximum')
            if minimum is not None and len(value) < minimum:
                errors.append((f'{field}.length', f"Field {field} is lower than {minimum}"))
            if maximum is not None and len(value) > maximum:
                errors.append((f'{field}.length', f"Field {field} is higher than {maximum}"))
        if confirmation:
            confirmation_field = f'{field}_confirmation'
            if confirmation_field in instance._virtual_fields:
                confirmation_value = instance._virtual_fields.get(confirmation_field)
                if confirmation_value != value:
                    errors.append((f'{field}.confirmation', f"Field {field} values do not match"))
    return errors


def _build(model_cls, base_instance):
    if base_instance is None:
        return None
    res = model_cls()
    res._base_instance = base_instance
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

    def where(self, **kwargs):
        self._query = self._query.filter_by(**kwargs)
        return self

    def first(self):
        s = session()
        res = s.execute(self._query).scalars().first()
        if not res:
            return None
        return _build(self._model_cls, res)

    def order(self, **kwargs):
        for k, v in kwargs.items():
            field = getattr(self._model_base, k)
            clause = field.desc() if v == 'desc' else field.asc()
            self._query = self._query.order_by(clause)
        return self

    def __iter__(self):
        s = session()
        res = s.execute(self._query).scalars()
        for r in res:
            yield _build(self._model_cls, r)

    def __repr__(self):
        return repr([r for r in self])


class Model:

    _fields = ['_virtual_fields', '_base_instance', '_errors']

    def __init__(self, **kwargs):
        base = _base(self.__class__)
        self._virtual_fields = {}
        self._base_instance = base()
        self._errors = []
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def errors(self):
        return self._errors

    @property
    def column_names(self):
        return list(self._base_instance.__table__.columns.keys())

    def __getattr__(self, name):
        if name in self._virtual_fields:
            return self._virtual_fields[name]
        return getattr(self._base_instance, name)

    def __setattr__(self, name, value):
        if name in self._fields:
            super().__setattr__(name, value)
            return
        ns = registry.get(self.__class__)
        vfd = ns.setdefault('virtual_fields', {})
        if name in vfd:
            self._virtual_fields[name] = value
            map_to = vfd[name].get('map_to')
            map_fn = vfd[name].get('map_fn')
            if map_to and map_fn:
                setattr(self._base_instance, map_to, map_fn(value))
        else:
            setattr(self._base_instance, name, value)

    def __json__(self):
        return {c: getattr(self._base_instance, c) for c in self.column_names}

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
    def find(cls, id):
        found = ModelQuery(cls).where(id=id).first()
        if not found:
            raise RecordNotFoundException(f"{cls.__name__} record with id {id} was not found")
        return found

    @classmethod
    def find_by(cls, **kwargs):
        return ModelQuery(cls).where(**kwargs).first()

    def update(self, **kwargs):
        for field, value in kwargs.items():
            setattr(self, field, value)
        return self.save()

    def save(self, validate=True):
        try:
            if validate:
                validate_rules = registry.get(self.__class__).get('validates') or []
                self._errors = []
                for vr in validate_rules:
                    self._errors.extend(vr(instance=self))
                if self._errors:
                    return False

            s = session()
            now = datetime.now(timezone.utc)
            if not self.is_persisted():
                self._base_instance.created_at = now
                s.add(self._base_instance)
            self._base_instance.updated_at = now
            s.flush()
            return True
        except Exception:
            _logger.exception(f'Error storing {self.__class__.__name__} instance')
            return False

    def is_persisted(self):
        return inspect(self._base_instance).persistent

    def destroy(self):
        s = session()
        s.delete(self._base_instance)
        s.flush()

    def __repr__(self) -> str:
        values = {c: getattr(self._base_instance, c) for c in self.column_names}
        return f'<{self.__class__.__name__}:{hex(id(self))} {values}>'
