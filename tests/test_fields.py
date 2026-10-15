import pytest
import sqlalchemy as sa

from flaskteroids.fields import fields


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("text", sa.Text),
        ("string", sa.String),
        ("str", sa.String),
        ("integer", sa.Integer),
        ("int", sa.Integer),
        ("float", sa.Float),
        ("boolean", sa.Boolean),
        ("bool", sa.Boolean),
        ("datetime", sa.DateTime),
        ("date", sa.Date),
        ("time", sa.Time),
        ("json", sa.JSON),
    ],
)
def test_generator_types_create_fresh_sqlalchemy_types(name, expected):
    first, second = fields[name](), fields[name]()
    assert isinstance(first, expected)
    assert isinstance(second, expected)
    assert first is not second


def test_string_length_and_aliases():
    assert fields["string"]().length == 255
    assert fields["string"] is fields["str"]
    assert fields["integer"] is fields["int"]
    assert fields["boolean"] is fields["bool"]


def test_supported_generator_types():
    assert set(fields) == {
        "text",
        "string",
        "str",
        "integer",
        "int",
        "float",
        "boolean",
        "bool",
        "datetime",
        "date",
        "time",
        "json",
    }
