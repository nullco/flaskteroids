from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Self

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import selectinload

from flaskteroids._models.associations import _get_association
from flaskteroids._models.records import _base, _build
from flaskteroids.db import session
from flaskteroids.exceptions import RecordNotFoundException

if TYPE_CHECKING:
    from flaskteroids.model import Model


class ModelQuery[QueryModel: "Model"]:
    def __init__(self, model_cls: type[QueryModel]) -> None:
        self._model_cls = model_cls
        self._model_base = _base(model_cls)
        self._query = select(self._model_base)
        self._limit = None
        self._offset = None

    def find(self, id) -> QueryModel:
        found = self.where(id=id).first()
        if not found:
            raise RecordNotFoundException(
                f"{self._model_cls.__name__} record with id {id} was not found"
            )
        return found

    def where(self, *args, **kwargs) -> Self:
        if args:
            self._query = self._query.filter(*args)
        if kwargs:
            self._query = self._query.filter_by(**kwargs)
        return self

    def includes(self, *args: str) -> Self:
        for rel in args:
            _get_association(self._model_cls, name=rel)
            self._query = self._query.options(
                selectinload(getattr(self._model_base, rel))
            )
        return self

    def all(self) -> Iterator[QueryModel]:
        yield from self.__iter__()

    def first(self) -> QueryModel | None:
        res = session.execute(self._query).scalars().first()
        if not res:
            return None
        return _build(self._model_cls, res)

    def last(self) -> QueryModel | None:
        if self._limit is not None or self._offset is not None:
            records = session.execute(self._query).scalars().all()
            return _build(self._model_cls, records[-1]) if records else None
        primary_key = inspect(self._model_base).primary_key[0]
        query = self._query.order_by(primary_key.desc())
        res = session.execute(query).scalars().first()
        if not res:
            return None
        return _build(self._model_cls, res)

    def count(self) -> int:
        query = select(func.count()).select_from(self._query.subquery())
        return session.execute(query).scalar_one()

    def order(self, **kwargs: str) -> Self:
        for k, v in kwargs.items():
            field = getattr(self._model_base, k)
            clause = field.desc() if v == "desc" else field.asc()
            self._query = self._query.order_by(clause)
        return self

    def limit(self, value: int | None) -> Self:
        self._query = self._query.limit(value)
        self._limit = value
        return self

    def offset(self, value: int | None) -> Self:
        self._query = self._query.offset(value)
        self._offset = value
        return self

    def __iter__(self) -> Iterator[QueryModel]:
        res = session.execute(self._query).scalars()
        for r in res:
            yield _build(self._model_cls, r)

    def __repr__(self) -> str:
        return repr([r for r in self])

    def to_sql(self) -> str:
        return str(self._query.compile(compile_kwargs={"literal_binds": True}))

    def __json__(self) -> list[Any]:
        res = session.execute(self._query).scalars()
        return [_build(self._model_cls, r).__json__() for r in res]
