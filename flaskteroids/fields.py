from abc import ABC
from contextlib import suppress
import sqlalchemy as sa
from datetime import datetime, date, time


class Field(ABC):
    def __init__(self, column_type, primitive_type) -> None:
        self.column_type = column_type
        self.primitive_type = primitive_type

    def new_column(self):
        return self.column_type()

    def as_primitive(self, value):
        if isinstance(value, self.primitive_type):
            return value
        with suppress(ValueError):
            return self.primitive_type(value)


class Text(Field):

    def __init__(self) -> None:
        super().__init__(sa.Text, str)


class String(Field):

    def __init__(self) -> None:
        super().__init__(sa.String, str)

    def new_column(self):
        return self.column_type(255)


class Integer(Field):

    def __init__(self) -> None:
        super().__init__(sa.Integer, int)


class Float(Field):

    def __init__(self) -> None:
        super().__init__(sa.Float, float)


class Boolean(Field):

    def __init__(self) -> None:
        super().__init__(sa.Boolean, bool)

    def as_primitive(self, value):
        false_values = {'false', 'f', 0, '0', False, None, ''}
        if value in false_values:
            return False
        return True


class DateTime(Field):

    def __init__(self) -> None:
        super().__init__(sa.DateTime, datetime)

    def as_primitive(self, value):
        with suppress(ValueError):
            if isinstance(value, datetime):
                return value
            elif isinstance(value, str):
                return datetime.fromisoformat(value)


class Date(Field):

    def __init__(self) -> None:
        super().__init__(sa.Date, datetime)

    def as_primitive(self, value):
        with suppress(ValueError):
            if isinstance(value, date):
                return value
            elif isinstance(value, str):
                return date.fromisoformat(value)


class Time(Field):

    def __init__(self) -> None:
        super().__init__(sa.Time, datetime)

    def as_primitive(self, value):
        with suppress(ValueError):
            if isinstance(value, time):
                return value
            elif isinstance(value, str):
                return time.fromisoformat(value)


class Json(Field):
    def __init__(self) -> None:
        super().__init__(sa.JSON, dict)


fields = {
    'text': Text(),
    'string': String(),
    'str': String(),
    'integer': Integer(),
    'float': Float(),
    'int': Integer(),
    'boolean': Boolean(),
    'bool': Boolean(),
    'datetime': DateTime(),
    'date': Date(),
    'time': Time(),
    'json': Json(),
}


def from_column_type(column_type):
    for f in fields.values():
        if isinstance(column_type, f.column_type):
            return f
    raise ValueError(f'Columm type <{column_type}> is not supported yet')
