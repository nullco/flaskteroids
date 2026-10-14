import pytest
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base

from flaskteroids.model import Error, Errors, Model, validates
from flaskteroids.rules import rules

Base = declarative_base()


class EntryTable(Base):
    __tablename__ = "entries"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    quantity = Column(Integer)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


@pytest.fixture
def entry_model(init_models):
    def prepare(*declarations):
        @rules(*declarations)
        class Entry(Model):
            threshold = 10

        init_models(Base, [(EntryTable, Entry)])
        return Entry

    return prepare


def test_errors_public_container():
    errors = Errors()
    assert not errors
    assert len(errors) == errors.count == 0
    errors.append(("name.presence", "name required"))
    errors.extend(iter([("name.length", "name too short"), ("quantity", "too low")]))
    assert errors
    assert len(errors) == errors.count == 3
    assert (
        errors.full_messages()
        == errors.__json__()
        == [
            "name required",
            "name too short",
            "too low",
        ]
    )
    assert Error(("field", "message")).full_message() == "message"


@pytest.mark.parametrize("presence", [None, False, {}])
def test_disabled_presence(entry_model, presence):
    entry = entry_model(validates("name", presence=presence)).new(name="")
    assert entry.save() is True
    assert not entry.errors


@pytest.mark.parametrize("length", [None, {}, {"minimum": 0, "maximum": 3}])
def test_length_allows_none(entry_model, length):
    entry = entry_model(validates("name", length=length)).new()
    assert entry.save() is True


def test_validation_order_messages_and_retry(entry_model):
    Entry = entry_model(
        validates("name", presence=True, length={"minimum": 2}),
        validates("quantity", comparison={"greater_than": 10, "equal_to": 20}),
    )
    entry = Entry.new(name="", quantity=5)
    assert entry.save() is False
    assert entry.errors.__json__() == [
        "Field name is blank",
        "Field name is lower than 2",
        "Field quantity must be greater than 10",
        "Field quantity must be equal to 20",
    ]
    assert entry.update(name="ok", quantity=20) is True
    assert not entry.errors


@pytest.mark.parametrize("attributes", [{}, {"name": None}])
def test_presence_rejects_omitted_and_explicit_null_attributes(entry_model, attributes):
    Entry = entry_model(validates("name", presence=True))
    entry = Entry.new(**attributes)

    assert entry.name is None
    assert entry.save() is False
    assert entry.errors.full_messages() == ["Field name is blank"]
    assert Entry.count() == 0


def test_presence_rejects_null_update_without_changing_persisted_value(entry_model):
    Entry = entry_model(validates("name", presence=True))
    entry = Entry.create(name="Existing")

    assert entry.update(quantity=1) is True
    assert entry.name == "Existing"
    assert entry.update(name=None) is False
    assert entry.name is None
    assert entry.errors.full_messages() == ["Field name is blank"]
    assert entry.reload().name == "Existing"


def test_custom_presence_message(entry_model):
    entry = entry_model(validates("name", presence={"message": "required"})).new()
    assert entry.save() is False
    assert entry.errors.full_messages() == ["required"]


def test_presence_dict_without_message_retains_current_error(entry_model):
    entry = entry_model(validates("name", presence={"unknown": True})).new()
    with pytest.raises(KeyError, match="message"):
        entry.save()


@pytest.mark.parametrize("confirmation", [False, True])
def test_confirmation_virtual_field_and_disabled_option(entry_model, confirmation):
    Entry = entry_model(validates("name", confirmation=confirmation))
    entry = Entry.new(name="first", name_confirmation="different")
    assert entry.save() is (not confirmation)
    assert entry.errors.full_messages() == (
        ["Field name values do not match"] if confirmation else []
    )
    assert entry.update(name_confirmation="first") is True


@pytest.mark.parametrize("operand", [10, "threshold", lambda: 10])
def test_comparison_operands(entry_model, operand):
    entry = entry_model(
        validates("quantity", comparison={"greater_than": operand})
    ).new(quantity=5)
    assert entry.save() is False
    assert entry.errors.full_messages() == ["Field quantity must be greater than 10"]


def test_incompatible_comparison_is_validation_error(entry_model):
    entry = entry_model(validates("quantity", comparison={"greater_than": list})).new(
        quantity=5
    )
    assert entry.save() is False
    assert entry.errors.full_messages() == ["Field quantity cannot be compared with []"]


@pytest.mark.parametrize(
    "comparison", [None, {}, {"greater_than": "absent"}, {"unknown": 1}]
)
def test_disabled_and_unresolved_comparisons(entry_model, comparison):
    entry = entry_model(validates("quantity", comparison=comparison)).new(quantity=5)
    assert entry.save() is True
