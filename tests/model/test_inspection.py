from datetime import UTC, date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import Column, Date, DateTime, Integer, String, Time
from sqlalchemy.orm import declarative_base

from tests.model.schema_support import model_base

Base = declarative_base()


class InspectionTable(Base):
    __tablename__ = "inspection_records"

    id = Column(Integer, primary_key=True)
    date_value = Column(Date)
    datetime_value = Column(DateTime(timezone=True))
    time_value = Column(Time(timezone=True))
    label = Column(String)
    quantity = Column(Integer)


@pytest.fixture
def record_model(init_models):
    class InspectionRecord(model_base(Base)):
        pass

    init_models(Base, [(InspectionTable, InspectionRecord)])
    return InspectionRecord


@pytest.mark.parametrize(
    "field, value, expected",
    [
        ("date_value", date(2026, 10, 16), "2026-10-16"),
        ("date_value", date(2024, 2, 29), "2024-02-29"),
        (
            "datetime_value",
            datetime(2026, 10, 16, 12, 30),
            "2026-10-16 12:30:00",
        ),
        (
            "datetime_value",
            datetime(2026, 10, 16, 12, 30, 1, 123456),
            "2026-10-16 12:30:01.123456",
        ),
        (
            "datetime_value",
            datetime(2026, 10, 16, 12, 30, 1, 123456, tzinfo=UTC),
            "2026-10-16 12:30:01.123456+00:00",
        ),
        (
            "datetime_value",
            datetime(
                2026, 10, 16, 12, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))
            ),
            "2026-10-16 12:30:00+05:30",
        ),
        (
            "datetime_value",
            datetime(2026, 10, 16, 12, 30, tzinfo=timezone(timedelta(hours=-4))),
            "2026-10-16 12:30:00-04:00",
        ),
        ("time_value", time(12, 30), "12:30:00"),
        ("time_value", time(12, 30, 1, 123456), "12:30:01.123456"),
        ("time_value", time(12, 30, tzinfo=UTC), "12:30:00+00:00"),
        (
            "time_value",
            time(12, 30, 1, 123456, tzinfo=timezone(timedelta(hours=5, minutes=30))),
            "12:30:01.123456+05:30",
        ),
    ],
)
def test_repr_formats_temporal_values_without_changing_json(
    record_model, field, value, expected
):
    record = record_model(**{field: value}).apply_changes()
    original_json = record.__json__()
    expected_values = {
        "id": None,
        "date_value": None,
        "datetime_value": None,
        "time_value": None,
        "label": None,
        "quantity": None,
    }
    expected_values[field] = expected

    assert repr(record) == f"<InspectionRecord:{hex(id(record))} {expected_values}>"
    assert record.__json__() == original_json
    assert record.__json__()[field] is value
    assert record.read_published_attribute(field) is value


def test_repr_formats_loaded_temporal_values(record_model, session):
    record = record_model.create(
        date_value=date(2026, 10, 16),
        datetime_value=datetime(2026, 10, 16, 12, 30, 1, 123456),
        time_value=time(12, 30, 1, 123456),
    )
    identity = record.id
    session.expunge(record)
    loaded = record_model.find(identity)
    expected = {
        "id": identity,
        "date_value": "2026-10-16",
        "datetime_value": "2026-10-16 12:30:01.123456",
        "time_value": "12:30:01.123456",
        "label": None,
        "quantity": None,
    }

    assert repr(loaded) == f"<InspectionRecord:{hex(id(loaded))} {expected}>"


def test_repr_preserves_other_values(record_model):
    record = record_model(label="Example", quantity=7).apply_changes()
    expected = {
        "id": None,
        "date_value": None,
        "datetime_value": None,
        "time_value": None,
        "label": "Example",
        "quantity": 7,
    }

    assert repr(record) == f"<InspectionRecord:{hex(id(record))} {expected}>"


def test_repr_temporal_values_remain_published_not_staged(record_model):
    record = record_model.create(datetime_value=datetime(2026, 10, 16, 12, 30))
    pending = datetime(2027, 1, 1, 9, 15)
    record.datetime_value = pending

    representation = repr(record)

    assert "'datetime_value': '2026-10-16 12:30:00'" in representation
    assert "2027-01-01" not in representation
    assert record.datetime_value is pending
    assert record.__json__()["datetime_value"] is pending
