import pytest

from flaskteroids.turbo import dom_class, dom_id
from tests.app.models.user import User
from tests.turbo.fixtures.records import Membership, Post


@pytest.mark.parametrize(
    "record,prefix,expected",
    [
        (Post, None, "new_post"),
        (Post(), None, "new_post"),
        (Post(1), None, "post_1"),
        (Post(0), None, "post_0"),
        (Post, "edit", "edit_post"),
        (Post(), "edit", "edit_post"),
        (Post(1), "edit", "edit_post_1"),
    ],
)
def test_dom_id_uses_record_keys_and_prefixes(record, prefix, expected):
    assert dom_id(record, prefix) == expected


@pytest.mark.parametrize("record", [Post, Post(), Post(1)])
def test_dom_class_uses_model_name_without_record_key(record):
    assert dom_class(record) == "post"
    assert dom_class(record, "edit") == "edit_post"


@pytest.mark.parametrize("record", [None, "post", 1, object()])
def test_dom_identifiers_reject_values_without_the_model_protocol(record):
    with pytest.raises(ValueError, match="model class or a record"):
        dom_id(record)
    with pytest.raises(ValueError, match="model class or a record"):
        dom_class(record)


def test_model_keys_are_available_before_save_and_after_destroy(app_ctx, monkeypatch):
    monkeypatch.setattr(User, "to_param", lambda self: "a-url-slug")
    unsaved = User(username="Reader")
    assert unsaved.to_key() is None
    assert dom_id(unsaved) == "new_user"
    assigned = User(id=123, username="Assigned")
    assert assigned.is_new_record()
    assert assigned.to_key() == [123]
    assert dom_id(assigned) == "user_123"

    record = User.create(username="Saved")
    key = record.to_key()
    assert key == [record.id]
    assert record.to_param() == "a-url-slug"
    assert dom_id(record) == f"user_{record.id}"
    assert record.destroy()
    assert record.to_key() == key
    assert dom_id(record) == f"user_{key[0]}"


@pytest.mark.parametrize(
    "values,key,identifier",
    [
        ({}, None, "new_membership"),
        ({"account_id": 3}, None, "new_membership"),
        ({"account_id": 3, "member_id": 0}, [3, 0], "membership_3_0"),
    ],
)
def test_composite_model_keys_require_all_components(values, key, identifier):
    record = Membership(**values)
    assert record.to_key() == key
    assert dom_id(record) == identifier


def test_model_partial_path_is_inferred_from_class_name():
    assert User.to_partial_path() == "users/user"
    assert Membership.to_partial_path() == "memberships/membership"
