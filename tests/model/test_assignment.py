import pytest
from flask import current_app
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base

from flaskteroids.helpers import form_with
from flaskteroids.model import (
    PasswordAuthenticator,
    after_initialize,
    has_secure_password,
    validates,
)
from flaskteroids.rules import rules
from tests.model.schema_support import model_base

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


ApplicationModel = model_base(
    Base,
    relationships={
        "User": {"group": {"argument": "Group", "back_populates": "users"}},
        "Group": {"users": {"argument": "User", "back_populates": "group"}},
    },
)


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


@rules(
    validates("group", presence=True),
    has_secure_password(),
    after_initialize("_prepare"),
)
class User(Customization, ApplicationModel, PasswordAuthenticator):
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


@rules(validates("name", presence=True))
class Group(ApplicationModel):
    pass


@pytest.fixture(autouse=True)
def models(init_models):
    init_models(Base, [(UserTable, User), (GroupTable, Group)])


@pytest.mark.parametrize("entry", ["direct", "constructor", "new", "create", "update"])
def test_assignment_rejects_unknown_attributes_before_persistence(entry):
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
        "registry",
        "metadata",
        "create",
        "find",
        "annotation_only",
        "password_reset_token",
        "_initialize",
        "_flaskteroids_model",
    ],
)
def test_assignment_rejects_read_only_and_protected_attributes(name):
    user = User.new()
    with pytest.raises(AttributeError, match=f"User.*{name}"):
        setattr(user, name, "secret-value")


@pytest.mark.parametrize("entry", ["constructor", "new", "create", "update"])
@pytest.mark.parametrize(
    "name", ["_base_instance", "_changes", "_fields", "_flaskteroids_rules", "save"]
)
def test_mass_assignment_rejects_framework_state_attributes(entry, name):
    user = User.new()
    with pytest.raises(AttributeError, match=f"User.*{name}"):
        if entry == "constructor":
            User(**{name: None})
        elif entry == "update":
            user.update(**{name: None})
        else:
            getattr(User, entry)(**{name: None})
    assert User.count() == 0


def test_transients_descriptors_and_private_caches_are_instance_local(mocker, session):
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
    assert User.find(user.id) is user
    session.expunge(user)
    loaded = User.find(user.id)
    assert loaded.delivery_hint is None
    assert loaded.category == "initialized"
    assert loaded._render_cache == {}
    assert "delivery_hint" not in user.__json__()
    assert "category" not in user.__json__()
    with current_app.test_request_context():
        html = form_with(
            model=user,
            url="/users",
            caller=lambda form: form.text_field("delivery_hint"),
        )
    assert "preview" not in html


def test_assignment_propagates_setter_exception():
    user = User.new()
    with pytest.raises(ValueError, match="^application setter failed$"):
        user.rejected = "secret-value"
    assert User.count() == 0


def test_assignment_casts_columns_and_invokes_virtual_setters():
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


def test_uncastable_input_is_retained_before_type_cast():
    user = User.new(age=42)
    value = object()
    user.age = value
    assert user.age is None
    assert user.read_attribute_before_type_cast("age") is value
    assert User.count() == 0


def test_belongs_to_reflects_assignment_reassignment_and_clearing():
    first = Group.create(name="first")
    second = Group.create(name="second")
    user = User.create(name="one", password="secret", group=first)
    user.group = second
    assert user.group.name == "second"
    assert user.group_id == first.id
    assert User.find(user.id) is user
    assert user.group is second
    assert user.save()
    assert user.reload().group.id == second.id
    user.group = None
    assert user.group is None
    assert user.group_id == second.id
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


def test_belongs_to_rejects_incorrect_target_model():
    user = User.new()
    with pytest.raises(TypeError, match="User.group.*Group"):
        user.group = User.new()
    assert user.group is None
    assert user.group_id is None


def test_native_collection_can_be_replaced():
    group = Group.new()
    user = User.new()
    group.users = [user]
    assert group.users == [user]
    assert user.group is group


def test_pending_association_reads_preserve_target_instance_state():
    group = Group.new(name="pending target")
    user = User.new(group=group)
    assert user.group is group
    assert user.group.name == "pending target"
    assert user.group_id is None
    assert Group.count() == 0
    assert User.count() == 0


def test_save_cascades_unsaved_target_with_validation_disabled():
    group = Group.new()
    user = User.new(name="one", password="secret", group=group)
    assert user.save() is False
    assert user.save(validate=False)
    assert group.id
    assert User.find(user.id).group.id == group.id
