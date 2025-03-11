from sqlalchemy import select
from flaskteroids.db import session


class ModelNotFoundException(Exception):
    pass


class Model:

    __basecls__ = None

    def __getattr__(self, name: str):
        if not self.__basecls__:
            raise Exception("""
                Model not configured properly.
                Make sure your class is inside app.models folder
            """)
        return getattr(self.__basecls__, name)

    @classmethod
    def all(cls):
        s = session()
        return s.execute(select(cls.__basecls__)).scalars().all()

    @classmethod
    def find(cls, id):
        s = session()
        return s.execute(
            select(cls.__basecls__).
            where(cls.__basecls__.id == id)
        ).scalars().first()

    @classmethod
    def find_or_fail(cls, id):
        res = cls.find(id)
        if not res:
            raise ModelNotFoundException("Instance not found")
        return res
