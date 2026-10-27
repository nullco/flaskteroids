from datetime import date
from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from flaskteroids.actions import JSONValue, Parameters
from flaskteroids.exceptions import InvalidParameter


@pytest.mark.parametrize(
    "value",
    [
        {"notifications": True, "groups": [{"limits": [1, None, False]}]},
        {},
        [],
        [{"name": "editors"}, ["one", 2], None],
        "dark",
        "",
        42,
        1.5,
        False,
        None,
    ],
)
def test_json_schema_permits_complete_json_values(value):
    params = Parameters.new({"post": {"settings": value, "admin": True}})

    assert params.expect(post=[("settings", JSONValue)]) == {"settings": value}
    assert params["post"] == {"settings": value, "admin": True}


@pytest.mark.parametrize(
    "value",
    [
        object(),
        date(2025, 1, 1),
        {1: "non-string key"},
        {"nested": object()},
        [{"nested": object()}],
        (1, 2),
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_json_schema_rejects_non_json_values(value):
    params = Parameters.new({"post": {"settings": value}})

    with pytest.raises(InvalidParameter):
        params.expect(post=[("settings", JSONValue)])


def test_json_schema_rejects_nested_uploads():
    with BytesIO(b"data") as stream:
        upload = FileStorage(stream, filename="file.txt")
        params = Parameters.new({"post": {"settings": {"files": [upload]}}})

        with pytest.raises(InvalidParameter):
            params.expect(post=[("settings", JSONValue)])


def test_json_schema_keeps_json_values_scoped_to_the_declared_field():
    params = Parameters.new(
        {"post": {"settings": {"nested": True}, "title": {"admin": True}}}
    )

    with pytest.raises(InvalidParameter):
        params.expect(post=["title", ("settings", JSONValue)])


def test_json_schema_preserves_omitted_fields():
    params = Parameters.new({"post": {"title": "Updated"}})

    assert params.expect(post=["title", ("settings", JSONValue)]) == {
        "title": "Updated"
    }
