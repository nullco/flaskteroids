import pytest
import sqlalchemy as sa
from datetime import datetime, date, time
from flaskteroids.fields import (
    Field, Text, String, Integer, Float, Boolean,
    DateTime, Date, Time, Json, fields, from_column_type
)


class TestField:

    def test_init(self):
        field = Field(sa.String, str)
        assert field.column_type == sa.String
        assert field.primitive_type == str

    def test_new_column(self):
        field = Field(sa.String, str)
        column = field.new_column()
        assert isinstance(column, sa.String)

    def test_as_primitive_already_primitive(self):
        field = Field(sa.String, str)
        assert field.as_primitive("test") == "test"

    def test_as_primitive_convertible(self):
        field = Field(sa.Integer, int)
        assert field.as_primitive("42") == 42

    def test_as_primitive_not_convertible(self):
        field = Field(sa.Integer, int)
        assert field.as_primitive("not_a_number") is None


class TestText:

    def test_init(self):
        field = Text()
        assert field.column_type == sa.Text
        assert field.primitive_type == str

    def test_new_column(self):
        field = Text()
        column = field.new_column()
        assert isinstance(column, sa.Text)


class TestString:

    def test_init(self):
        field = String()
        assert field.column_type == sa.String
        assert field.primitive_type == str

    def test_new_column(self):
        field = String()
        column = field.new_column()
        assert isinstance(column, sa.String)
        assert column.length == 255


class TestInteger:

    def test_init(self):
        field = Integer()
        assert field.column_type == sa.Integer
        assert field.primitive_type == int

    def test_new_column(self):
        field = Integer()
        column = field.new_column()
        assert isinstance(column, sa.Integer)


class TestFloat:

    def test_init(self):
        field = Float()
        assert field.column_type == sa.Float
        assert field.primitive_type == float

    def test_new_column(self):
        field = Float()
        column = field.new_column()
        assert isinstance(column, sa.Float)


class TestBoolean:

    def test_init(self):
        field = Boolean()
        assert field.column_type == sa.Boolean
        assert field.primitive_type == bool

    def test_new_column(self):
        field = Boolean()
        column = field.new_column()
        assert isinstance(column, sa.Boolean)

    @pytest.mark.parametrize("value,expected", [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("true", True),
        ("false", False),
        ("f", False),
        ("0", False),
        ("", False),
        (None, False),
        ("anything_else", True),
    ])
    def test_as_primitive(self, value, expected):
        field = Boolean()
        assert field.as_primitive(value) == expected


class TestDateTime:

    def test_init(self):
        field = DateTime()
        assert field.column_type == sa.DateTime
        assert field.primitive_type == datetime

    def test_new_column(self):
        field = DateTime()
        column = field.new_column()
        assert isinstance(column, sa.DateTime)

    def test_as_primitive_datetime(self):
        field = DateTime()
        dt = datetime(2023, 1, 1, 12, 0, 0)
        assert field.as_primitive(dt) == dt

    def test_as_primitive_string(self):
        field = DateTime()
        dt = field.as_primitive("2023-01-01T12:00:00")
        assert dt == datetime(2023, 1, 1, 12, 0, 0)

    def test_as_primitive_invalid_string(self):
        field = DateTime()
        assert field.as_primitive("invalid") is None


class TestDate:

    def test_init(self):
        field = Date()
        assert field.column_type == sa.Date
        assert field.primitive_type == date

    def test_new_column(self):
        field = Date()
        column = field.new_column()
        assert isinstance(column, sa.Date)

    def test_as_primitive_date(self):
        field = Date()
        d = date(2023, 1, 1)
        assert field.as_primitive(d) == d

    def test_as_primitive_string(self):
        field = Date()
        d = field.as_primitive("2023-01-01")
        assert d == date(2023, 1, 1)

    def test_as_primitive_invalid_string(self):
        field = Date()
        assert field.as_primitive("invalid") is None


class TestTime:

    def test_init(self):
        field = Time()
        assert field.column_type == sa.Time
        assert field.primitive_type == time

    def test_new_column(self):
        field = Time()
        column = field.new_column()
        assert isinstance(column, sa.Time)

    def test_as_primitive_time(self):
        field = Time()
        t = time(12, 0, 0)
        assert field.as_primitive(t) == t

    def test_as_primitive_string(self):
        field = Time()
        t = field.as_primitive("12:00:00")
        assert t == time(12, 0, 0)

    def test_as_primitive_invalid_string(self):
        field = Time()
        assert field.as_primitive("invalid") is None


class TestJson:

    def test_init(self):
        field = Json()
        assert field.column_type == sa.JSON
        assert field.primitive_type == dict

    def test_new_column(self):
        field = Json()
        column = field.new_column()
        assert isinstance(column, sa.JSON)


class TestFieldsDict:

    def test_fields_dict_keys(self):
        expected_keys = {
            'text', 'string', 'str', 'integer', 'float', 'int',
            'boolean', 'bool', 'datetime', 'date', 'time', 'json'
        }
        assert set(fields.keys()) == expected_keys

    def test_fields_dict_values_types(self):
        for field in fields.values():
            assert isinstance(field, Field)

    def test_aliases(self):
        assert isinstance(fields['str'], String)
        assert isinstance(fields['string'], String)
        assert isinstance(fields['int'], Integer)
        assert isinstance(fields['integer'], Integer)
        assert isinstance(fields['bool'], Boolean)
        assert isinstance(fields['boolean'], Boolean)


class TestFromColumnType:

    def test_from_column_type_text(self):
        column = sa.Text()
        field = from_column_type(column)
        assert isinstance(field, Text)

    def test_from_column_type_string(self):
        column = sa.String()
        field = from_column_type(column)
        assert isinstance(field, String)

    def test_from_column_type_integer(self):
        column = sa.Integer()
        field = from_column_type(column)
        assert isinstance(field, Integer)

    def test_from_column_type_float(self):
        column = sa.Float()
        field = from_column_type(column)
        assert isinstance(field, Float)

    def test_from_column_type_boolean(self):
        column = sa.Boolean()
        field = from_column_type(column)
        assert isinstance(field, Boolean)

    def test_from_column_type_datetime(self):
        column = sa.DateTime()
        field = from_column_type(column)
        assert isinstance(field, DateTime)

    def test_from_column_type_date(self):
        column = sa.Date()
        field = from_column_type(column)
        assert isinstance(field, Date)

    def test_from_column_type_time(self):
        column = sa.Time()
        field = from_column_type(column)
        assert isinstance(field, Time)

    def test_from_column_type_json(self):
        column = sa.JSON()
        field = from_column_type(column)
        assert isinstance(field, Json)

    def test_from_column_type_unsupported(self):
        column = sa.Column(sa.String())
        with pytest.raises(ValueError, match="Columm type .* is not supported yet"):
            from_column_type(column)
