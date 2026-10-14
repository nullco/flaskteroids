import pytest
from flask import current_app
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base

from flaskteroids.helpers import form_with
from flaskteroids.model import (
    Model,
    PasswordAuthenticator,
    after_initialize,
    belongs_to,
    has_many,
    has_secure_password,
)
from flaskteroids.rules import rules

Base = declarative_base()


class UserTable(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    age = Column(Integer)
    password_digest = Column(String)
    group_id = Column(Integer, ForeignKey("groups.id"))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class GroupTable(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class DisplayName:
    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.name

    def __set__(self, instance, value):
        instance.name = value.upper()


class Customization:
    delivery_hint = None
    display_name = DisplayName()

    @property
    def normalized_name(self):
        raise AssertionError("Assignment must not evaluate the getter")

    @normalized_name.setter
    def normalized_name(self, value):
        self.name = value.strip()


@rules(belongs_to("group"), has_secure_password(), after_initialize("_prepare"))
class User(Customization, Model, PasswordAuthenticator):
    category = "ordinary"
    annotation_only: str

    def _prepare(self):
        self._render_cache = {}
        self.category = "initialized"

    @property
    def label(self):
        return self.name

    @property
    def rejected(self):
        return None

    @rejected.setter
    def rejected(self, value):
        raise ValueError("application setter failed")

    def greet(self):
        return "hello"


@rules(has_many("users"))
class Group(Model):
    pass


@pytest.fixture(autouse=True)
def models(init_models):
    init_models(Base, [(UserTable, User), (GroupTable, Group)])


@pytest.mark.parametrize("entry", ["direct", "constructor", "new", "create", "update"])
def test_unknown_assignment_fails_without_saving(entry):
    group = Group.create(name="default")
    user = User.create(name="original", password="secret", group=group)
    with pytest.raises(AttributeError, match="User.*naem") as raised:
        if entry == "direct":
            user.naem = "private-value"
        elif entry == "constructor":
            User(naem="private-value")
        elif entry == "update":
            user.update(name="not saved", naem="private-value")
        else:
            getattr(User, entry)(naem="private-value")
    assert "private-value" not in str(raised.value)
    assert User.count() == 1
    assert User.find(user.id).name == "original"


@pytest.mark.parametrize(
    "name",
    [
        "label",
        "greet",
        "save",
        "errors",
        "column_names",
        "annotation_only",
        "password_reset_token",
        "_initialize",
        "_fields",
        "_flaskteroids_model",
    ],
)
def test_read_only_and_protected_attributes(name):
    user = User.new()
    with pytest.raises(AttributeError, match=f"User.*{name}"):
        setattr(user, name, "secret-value")


@pytest.mark.parametrize("entry", ["constructor", "new", "create", "update"])
@pytest.mark.parametrize(
    "name", ["_base_instance", "_changes", "_fields", "_flaskteroids_rules", "save"]
)
def test_mass_assignment_cannot_replace_framework_state(entry, name):
    user = User.new()
    with pytest.raises(AttributeError, match=f"User.*{name}"):
        if entry == "constructor":
            User(**{name: None})
        elif entry == "update":
            user.update(**{name: None})
        else:
            getattr(User, entry)(**{name: None})
    assert User.count() == 0


def test_transients_descriptors_and_private_caches_are_instance_local(mocker):
    group = Group.create(name="default")
    user = User.create(
        name="one", password="secret", delivery_hint="preview", group=group
    )
    assert user.category == "initialized"
    user.display_name = "alice"
    assert user.name == "ALICE"
    user.normalized_name = "  Bob  "
    assert user.name == "Bob"
    user._render_cache["key"] = "cached"
    assert user.save()
    user.reload()
    assert user.delivery_hint == "preview"
    assert user._render_cache == {"key": "cached"}
    loaded = User.find(user.id)
    assert loaded.delivery_hint is None
    assert loaded.category == "initialized"
    assert loaded._render_cache == {}
    assert "delivery_hint" not in user.__json__()
    assert "category" not in user.__json__()
    mocker.patch("flaskteroids.helpers.url_for", return_value="/users/")
    with current_app.test_request_context():
        html = form_with(
            model=user, caller=lambda form: form.text_field("delivery_hint")
        )
    assert "preview" not in html


def test_setter_exception_is_unchanged():
    user = User.new()
    with pytest.raises(ValueError, match="^application setter failed$"):
        user.rejected = "secret-value"
    assert User.count() == 0


def test_column_conversion_and_virtual_setters():
    group = Group.create(name="default")
    user = User.create(
        name="one",
        age="42",
        password="secret",
        password_confirmation="secret",
        group=group,
    )
    assert user.age == 42
    assert user.authenticate("secret")
    assert user.update(age="43")
    assert user.reload().age == 43


def test_rejected_column_conversion_keeps_previous_value():
    user = User.new(age=42)
    with pytest.raises(TypeError):
        user.age = object()
    assert user.age == 42
    assert User.count() == 0


def test_belongs_to_read_after_write_reassignment_and_clear():
    first = Group.create(name="first")
    second = Group.create(name="second")
    user = User.create(name="one", password="secret", group=first)
    user.group = second
    assert user.group.name == "second"
    assert user.group_id == second.id
    assert User.find(user.id).group.id == first.id
    assert user.save()
    assert user.reload().group.id == second.id
    user.group = None
    assert user.group is None
    assert user.group_id is None
    assert user.save() is False
    assert user.errors
    assert user.save(validate=False)
    assert user.reload().group is None
    assert user.group_id is None


@pytest.mark.parametrize("value", [1, "secret-value", object(), []])
def test_invalid_belongs_to_assignment_keeps_both_values(value):
    group = Group.create(name="first")
    user = User.create(password="secret", group=group)
    with pytest.raises(TypeError, match="User.group.*Group"):
        user.group = value
    assert user.group.id == group.id
    assert user.group_id == group.id
    assert user.save()
    assert user.reload().group.id == group.id


def test_wrong_model_is_not_an_association_target():
    user = User.new()
    with pytest.raises(TypeError, match="User.group.*Group"):
        user.group = User.new()
    assert user.group is None
    assert user.group_id is None


def test_has_many_replacement_explains_supported_api():
    group = Group.new()
    with pytest.raises(AttributeError, match="Group.users.*Relation.*create"):
        group.users = []


def test_pending_association_reads_preserve_target_instance_state():
    group = Group.new(name="pending target")
    user = User.new(group=group)
    assert user.group is group
    assert user.group.name == "pending target"
    assert user.group_id is None
    assert Group.count() == 0
    assert User.count() == 0


def test_existing_unsaved_target_cascade_with_validation_disabled():
    group = Group.new()
    user = User.new(name="one", password="secret", group=group)
    assert user.save() is False
    assert user.save(validate=False)
    assert group.id
    assert User.find(user.id).group.id == group.id
