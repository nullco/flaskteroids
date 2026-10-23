from __future__ import annotations

from collections.abc import Iterator
from copy import copy
from typing import TYPE_CHECKING, Self

from flask import current_app
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import selectinload

from flaskteroids.db import session
from flaskteroids.declarations import model_for
from flaskteroids.exceptions import RecordNotFoundException

if TYPE_CHECKING:
    from flaskteroids.model import Model


class ModelQuery[QueryModel: "Model"]:
    """Immutable, lazy facade over a native SQLAlchemy Select."""

    def __init__(self, model_cls: type[QueryModel]) -> None:
        self._model_cls = model_cls.prepare()
        self.statement = select(model_cls).order_by(*inspect(model_cls).primary_key)
        self._ordered = False
        self._limit = None
        self._creation_attributes = {}

    def _with(self, statement):
        result = copy(self)
        result.statement = statement
        return result

    def _session(self):
        current_app.extensions["flaskteroids.db"].require_model(self._model_cls)
        return session

    def where(self, *expressions, **filters) -> Self:
        if names := filters.keys() & model_for(self._model_cls).rich_texts:
            raise ValueError(
                f"Rich-text attributes are not searchable scalar columns: {sorted(names)}"
            )
        result = self._with(self.statement.where(*expressions).filter_by(**filters))
        result._creation_attributes = self._creation_attributes | filters
        return result

    def new(self, **attributes) -> QueryModel:
        return self._model_cls.new(**(self._creation_attributes | attributes))

    def create(self, **attributes) -> QueryModel:
        record = self.new(**attributes)
        record.save()
        return record

    def first_or_create(self, **attributes) -> QueryModel:
        record = self.first()
        return record if record is not None else self.create(**attributes)

    def includes(self, *paths: str) -> Self:
        options = []
        for path in paths:
            if (
                not isinstance(path, str)
                or not path
                or any(not part for part in path.split("."))
            ):
                raise ValueError(
                    "includes() expects nonempty dotted relationship paths"
                )
            model, option = self._model_cls, None
            for name in path.split("."):
                relationship = inspect(model).relationships.get(name)
                if relationship is None:
                    raise AttributeError(
                        f"Unknown relationship {model.__name__}.{name}"
                    )
                attribute = getattr(model, name)
                option = (
                    selectinload(attribute)
                    if option is None
                    else option.selectinload(attribute)
                )
                model = relationship.mapper.class_
            options.append(option)
        return self.options(*options)

    def with_all_rich_text(self) -> Self:
        return self.includes(
            *(
                f"rich_text_{name}"
                for name in sorted(model_for(self._model_cls).rich_texts)
            )
        )

    def __getattr__(self, name):
        prefix = "with_rich_text_"
        if (
            name.startswith(prefix)
            and name[len(prefix) :] in model_for(self._model_cls).rich_texts
        ):
            return lambda: self.includes(f"rich_text_{name[len(prefix) :]}")
        raise AttributeError(f"{type(self).__name__} has no attribute {name!r}")

    def options(self, *options) -> Self:
        return self._with(self.statement.options(*options))

    def order(self, *expressions, **directions: str) -> Self:
        clauses = list(expressions)
        for name, direction in directions.items():
            if direction not in {"asc", "desc"}:
                raise ValueError("Order direction must be 'asc' or 'desc'")
            attribute = getattr(self._model_cls, name)
            clauses.append(attribute.desc() if direction == "desc" else attribute.asc())
        statement = self.statement if self._ordered else self.statement.order_by(None)
        result = self._with(statement.order_by(*clauses))
        result._ordered = True
        return result

    def limit(self, value: int | None) -> Self:
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("Limit must be a nonnegative integer or None")
        result = self._with(self.statement.limit(value))
        result._limit = value
        return result

    def offset(self, value: int | None) -> Self:
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("Offset must be a nonnegative integer or None")
        return self._with(self.statement.offset(value))

    def all(self) -> Self:
        """Return this scope without executing it."""
        return self

    def _load_records(self) -> list[QueryModel]:
        return self._session().execute(self.statement).scalars().unique().all()

    def first(self) -> QueryModel | None:
        if self._limit == 0:
            return None
        return (
            self._session().execute(self.statement.limit(1)).scalars().unique().first()
        )

    def last(self) -> QueryModel | None:
        # Honor explicit ordering and pagination instead of silently replacing it.
        records = self._load_records()
        return records[-1] if records else None

    def count(self) -> int:
        statement = select(func.count()).select_from(
            self.statement.order_by(None).subquery()
        )
        return self._session().execute(statement).scalar_one()

    def find(self, id) -> QueryModel:
        primary_key = inspect(self._model_cls).primary_key
        identity = id if isinstance(id, tuple) else (id,)
        if len(identity) != len(primary_key):
            raise ValueError("Identity must match the model's primary key")
        found = self.where(
            *(
                column == value
                for column, value in zip(primary_key, identity, strict=True)
            )
        ).first()
        if found is None:
            raise RecordNotFoundException(
                f"{self._model_cls.__name__} record with id {id} was not found"
            )
        return found

    def __iter__(self) -> Iterator[QueryModel]:
        return iter(self._load_records())

    def __repr__(self) -> str:
        return repr(self._load_records())

    def to_sql(self) -> str:
        return str(self.statement.compile(compile_kwargs={"literal_binds": True}))

    def __json__(self) -> list:
        return [record.__json__() for record in self]
