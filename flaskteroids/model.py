import logging
from sqlalchemy import select, inspect
from flaskteroids.db import session

_logger = logging.getLogger(__name__)


class ModelNotFoundException(Exception):
    pass


class Model:

    __base_cls__ = None

    @classmethod
    def __init_base__(cls, base):
        cls.__base_cls__ = base

    def __init__(self, **kwargs):
        base = self._base()
        self._base_instance = base(**kwargs)

    def getattr(self, name):
        return getattr(self._base_instance, name)

    @classmethod
    def _base(cls):
        if not cls.__base_cls__:
            raise Exception('Model not configured properly, make sure you have put it inside app.models folder')
        return cls.__base_cls__

    @classmethod
    def new(cls, **kwargs):
        instance = cls(**kwargs)
        return instance

    @classmethod
    def all(cls):
        base = cls._base()
        s = session()
        return s.execute(select(base)).scalars().all()

    @classmethod
    def find(cls, id):
        s = session()
        base = cls._base()
        return s.execute(
            select(base).
            where(base.id == id)
        ).scalars().first()

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

    def save(self):
        try:
            s = session()
            if not self.is_persisted():
                s.add(self._base_instance)
            s.flush()
            return True
        except Exception:
            _logger.exception('Error storing model instance')
            return False

    def is_persisted(self):
        return inspect(self._base_instance).persistent

    def destroy(self):
        s = session()
        s.remove(self._base_instance)
        s.flush()
