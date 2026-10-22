import pytest
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base

from flaskteroids.model import Error, Errors, validates
from tests.model.schema_support import model_base

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
    def prepare(*validations):
        class Entry(model_base(Base)):
            threshold = 10
            for field, options in validations:
                validates(field, **options)

        init_models(Base, [(EntryTable, Entry)])
        return Entry

    return prepare


def test_errors_collect_messages_and_support_public_container_operations():
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
def test_presence_validation_accepts_values_when_disabled(entry_model, presence):
    entry = entry_model(("name", {"presence": presence})).new(name="   ")
    assert entry.save() is True
    assert not entry.errors


@pytest.mark.parametrize("length", [None, {}, {"minimum": 0, "maximum": 3}])
def test_length_allows_none(entry_model, length):
    entry = entry_model(("name", {"length": length})).new()
    assert entry.save() is True


def test_validation_preserves_message_order_and_allows_retry(entry_model):
    Entry = entry_model(
        ("name", {"presence": True}),
        ("name", {"length": {"minimum": 2}}),
        ("quantity", {"comparison": {"greater_than": 10, "equal_to": 20}}),
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
    Entry = entry_model(("name", {"presence": True}))
    entry = Entry.new(**attributes)

    assert entry.name is None
    assert entry.save() is False
    assert entry.errors
    assert Entry.count() == 0


@pytest.mark.parametrize("name", ["", "   ", "\t\n\r", "\u00a0", "\u2003\u3000"])
def test_presence_rejects_blank_strings(entry_model, name):
    Entry = entry_model(("name", {"presence": True}))
    entry = Entry.new(name=name)

    assert entry.save() is False
    assert entry.name == name
    assert entry.errors
    assert Entry.count() == 0


@pytest.mark.parametrize(
    "name", ["hello", " hello ", "\t hello\n", "\u00a0hello\u3000"]
)
def test_presence_preserves_nonblank_strings(entry_model, name):
    Entry = entry_model(("name", {"presence": True}))
    entry = Entry.new(name=name)

    assert entry.save() is True
    assert not entry.errors
    assert entry.reload().name == name


def test_presence_accepts_zero(entry_model):
    entry = entry_model(("quantity", {"presence": True})).new(quantity=0)

    assert entry.save() is True
    assert not entry.errors
    assert entry.reload().quantity == 0


@pytest.mark.parametrize("name", [None, "   ", "\t\n", "\u00a0"])
def test_presence_rejects_blank_update_without_changing_persisted_value(
    entry_model, name
):
    Entry = entry_model(("name", {"presence": True}))
    entry = Entry.create(name="Existing")

    assert entry.update(quantity=1) is True
    assert entry.name == "Existing"
    assert entry.update(name=name) is False
    assert entry.name == name
    assert entry.errors
    assert entry.reload().name == "Existing"


def test_presence_validation_uses_custom_message(entry_model):
    entry = entry_model(("name", {"presence": {"message": "required"}})).new()
    assert entry.save() is False
    assert entry.errors.full_messages() == ["required"]


@pytest.mark.parametrize("confirmation", [False, True])
def test_confirmation_validation_supports_virtual_field_and_disabled_option(
    entry_model, confirmation
):
    Entry = entry_model(("name", {"confirmation": confirmation}))
    entry = Entry.new(name="first", name_confirmation="different")
    assert entry.save() is (not confirmation)
    assert bool(entry.errors) is confirmation
    assert entry.update(name_confirmation="first") is True


@pytest.mark.parametrize("operand", [10, "threshold", lambda: 10])
def test_comparison_validation_resolves_supported_operands(entry_model, operand):
    entry = entry_model(("quantity", {"comparison": {"greater_than": operand}})).new(
        quantity=5
    )
    assert entry.save() is False
    assert entry.errors
    assert entry.update(quantity=15) is True


def test_incompatible_comparison_is_validation_error(entry_model):
    entry = entry_model(("quantity", {"comparison": {"greater_than": list}})).new(
        quantity=5
    )
    assert entry.save() is False
    assert entry.errors


@pytest.mark.parametrize(
    "comparison", [None, {}, {"greater_than": "absent"}, {"unknown": 1}]
)
def test_comparison_validation_skips_disabled_and_unresolved_operands(
    entry_model, comparison
):
    entry = entry_model(("quantity", {"comparison": comparison})).new(quantity=5)
    assert entry.save() is True
