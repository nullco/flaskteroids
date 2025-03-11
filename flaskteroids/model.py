from sqlalchemy import select
from flaskteroids.db import session


class ModelNotFoundException(Exception):
    pass


class Model:

    __base_cls__ = None

    @classmethod
    def __init_base__(cls, base):
        cls.__base_cls__ = base

    def __init__(self, **kwargs):
        base = self._base()
        self._instance = base(**kwargs)

    def getattr(self, name):
        return getattr(self._instance, name)

    @classmethod
    def _base(cls):
        if not cls.__base_cls__:
            raise Exception('Model not configured properly, make sure you have put it inside app.models folder')
        return cls.__base_cls__

    @classmethod
    def create(cls, **kwargs):
        instance = cls(**kwargs)
        s = session()
        s.add(instance._instance)
        s.commit()
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
