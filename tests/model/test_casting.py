from datetime import date, datetime, time

import pytest
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    Time,
    cast,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base

from flaskteroids.model import Model

Base = declarative_base()


class EntryTable(Base):
    __tablename__ = "entries"

    id = Column(Integer, primary_key=True)
    required_value = Column(String, nullable=False)
    string_value = Column(String)
    text_value = Column(Text)
    integer_value = Column(Integer)
    float_value = Column(Float)
    boolean_value = Column(Boolean)
    datetime_value = Column(DateTime)
    date_value = Column(Date)
    time_value = Column(Time)
    json_value = Column(JSON)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class Entry(Model):
    pass


VALUES = [
    ("string_value", "Existing"),
    ("text_value", "Existing text"),
    ("integer_value", 42),
    ("float_value", 1.5),
    ("boolean_value", True),
    ("datetime_value", datetime(2023, 1, 1, 12)),
    ("date_value", date(2023, 1, 1)),
    ("time_value", time(12)),
    ("json_value", {"key": "value"}),
]


@pytest.fixture(autouse=True)
def models(init_models):
    init_models(Base, [(EntryTable, Entry)])


@pytest.mark.parametrize("attribute", [attribute for attribute, _ in VALUES])
def test_explicit_null_on_new_record_survives_save_and_reload(attribute):
    entry = Entry.new(required_value="Required", **{attribute: None})

    assert getattr(entry, attribute) is None
    assert entry.__json__()[attribute] is None
    assert entry.save() is True
    assert entry.is_persisted()
    assert getattr(entry.reload(), attribute) is None
    assert getattr(Entry.find(entry.id), attribute) is None


@pytest.mark.parametrize("attribute, value", VALUES)
@pytest.mark.parametrize("operation", ["assignment", "update"])
def test_explicit_null_clears_existing_attribute(attribute, value, operation):
    entry = Entry.create(required_value="Required", **{attribute: value})
    assert getattr(entry.reload(), attribute) == value

    if operation == "assignment":
        setattr(entry, attribute, None)
        assert getattr(entry, attribute) is None
        assert entry.save() is True
    else:
        assert entry.update(**{attribute: None}) is True

    assert getattr(entry.reload(), attribute) is None
    assert getattr(Entry.find(entry.id), attribute) is None


@pytest.mark.parametrize("attribute, value", VALUES)
def test_update_omitting_attribute_preserves_existing_value(attribute, value):
    entry = Entry.create(required_value="Required", **{attribute: value})

    assert entry.update(required_value="Updated") is True
    assert getattr(entry.reload(), attribute) == value


def test_non_nullable_column_rejects_explicit_null_on_creation(session):
    entry = Entry.new(required_value=None)

    with pytest.raises(IntegrityError):
        entry.save()
    session.rollback()
    assert Entry.count() == 0


def test_non_nullable_column_rejects_explicit_null_on_update(session):
    entry = Entry.create(required_value="Required")
    session.commit()

    with pytest.raises(IntegrityError):
        entry.update(required_value=None)
    session.rollback()
    assert entry.reload().required_value == "Required"


def test_json_none_uses_json_null_without_changing_storage_semantics(engine, session):
    entry = Entry.create(required_value="Required", json_value=None)
    session.commit()

    with engine.connect() as connection:
        stored = connection.execute(
            select(
                EntryTable.json_value.is_(None), cast(EntryTable.json_value, String)
            ).where(EntryTable.id == entry.id)
        ).one()

    assert stored == (False, "null")
    assert entry.reload().json_value is None
