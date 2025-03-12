import logging
from sqlalchemy import select, inspect
from flaskteroids.db import session
import flaskteroids.registry as registry

_logger = logging.getLogger(__name__)


class ModelNotFoundException(Exception):
    pass


def validate(field, *, required=False):
    def setup_rule(cls):
        def _validate(instance):
            errors = []
            value = getattr(instance, field) if hasattr(instance, field) else None
            if required:
                if value is None:
                    errors.append((f'{field}.required', f"Field {field} is required"))
                    return errors
            return errors
        ns = registry.get(cls)
        if 'validate' not in ns:
            ns['validate'] = []
        ns['validate'].append(_validate)
    return setup_rule


class Model:

    def __init__(self, **kwargs):
        base = self._base()
        self._errors = []
        self._base_instance = base(**kwargs)

    @property
    def errors(self):
        return self._errors

    def __getattr__(self, name):
        return getattr(self._base_instance, name)

    @classmethod
    def _base(cls):
        base = registry.get(cls).get('base_class')
        if not base:
            raise Exception('Model not configured properly, make sure you have put it inside app.models folder')
        return base

    @classmethod
    def _from_base_instance(cls, base_instance):
        if base_instance is None:
            return None
        res = cls()
        res._base_instance = base_instance
        return res

    @classmethod
    def new(cls, **kwargs):
        instance = cls(**kwargs)
        return instance

    @classmethod
    def all(cls):
        base = cls._base()
        s = session()
        return [cls._from_base_instance(r) for r in s.execute(select(base)).scalars().all()]

    @classmethod
    def find(cls, id):
        s = session()
        base = cls._base()
        return cls._from_base_instance(
            s.execute(
                select(base).
                where(base.id == id)
            ).scalars().first()
        )

    @classmethod
    def find_or_fail(cls, id):
        res = cls.find(id)
        if not res:
            raise ModelNotFoundException("Instance not found")
        return res

    def update(self, **kwargs):
        for field, value in kwargs.items():
            setattr(self._base_instance, field, value)
        return self.save()

    def save(self, validate=True):
        try:
            if validate:
                validate_rules = registry.get(self.__class__).get('validate')
                self._errors = []
                for vr in validate_rules:
                    self._errors.extend(vr(self))
                if self._errors:
                    return False

            s = session()
            if not self.is_persisted():
                s.add(self._base_instance)
            s.flush()
            return True
        except Exception:
            _logger.exception(f'Error storing {self.__name__} instance')
            return False

    def is_persisted(self):
        return inspect(self._base_instance).persistent

    def destroy(self):
        s = session()
        s.delete(self._base_instance)
        s.flush()
