import pytest
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base

from flaskteroids.model import (
    ModelQuery,
    RecordNotFoundException,
    after_find,
    after_initialize,
    init,
    validates,
)
from tests.model.schema_support import model_base

Base = declarative_base()


class ParentTable(Base):
    __tablename__ = "parents"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class ChildTable(Base):
    __tablename__ = "children"

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("parents.id"))
    name = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


@pytest.fixture
def family(init_models):
    events = []

    ApplicationModel = model_base(
        Base,
        relationships={
            "Parent": {
                "children": {
                    "argument": "Child",
                    "back_populates": "parent",
                    "cascade": "all, delete-orphan",
                }
            },
            "Child": {"parent": {"argument": "Parent", "back_populates": "children"}},
        },
    )

    class Parent(ApplicationModel):
        pass

    class Child(ApplicationModel):
        validates("name", presence=True)
        after_initialize("_initialized")
        after_find("_found")

        def __init__(self, **kwargs):
            events.append("constructor")
            super().__init__(**kwargs)

        def _initialized(self):
            events.append(("initialize", self.name))

        def _found(self):
            events.append(("find", self.name))

        def __json__(self):
            return {"label": self.name}

    init_models(Base, [(ParentTable, Parent), (ChildTable, Child)])
    return Parent, Child, events


def test_relations_validate_creation_maintain_inverse_and_cascade_deletion(family):
    Parent, Child, _ = family
    parent = Parent.create(name="parent")
    assert isinstance(parent.children, list)
    invalid = Child.create(parent=parent)
    assert invalid.is_new_record()
    assert invalid.errors
    assert invalid in parent.children
    assert Child.count() == 0
    parent.children.remove(invalid)
    assert not parent.children
    child = Child.create(name="child", parent=parent)
    assert child.is_persisted()
    assert child.parent.id == parent.id
    assert [entry.id for entry in parent.children] == [child.id]
    parent.destroy()
    assert Child.count() == 0


def test_initialization_is_idempotent_and_native_new_targets_cascade(family):
    Parent, Child, _ = family
    init(Child)
    init(Child)
    child = Child.new(name="child", parent=Parent.new(name="unsaved"))
    assert child.save() is True
    assert child.parent.is_persisted()
    assert not child.errors


@pytest.mark.parametrize("load", ["find", "query", "relation", "includes"])
def test_loaded_records_run_find_and_initialize_callbacks_once(family, load, session):
    Parent, Child, events = family
    parent = Parent.create(name="parent")
    child = Child.create(name="child", parent=parent)
    events.clear()
    session.expunge_all()
    if load == "find":
        loaded = Child.find(child.id)
    elif load == "query":
        loaded = list(Child.all())[0]
    elif load == "relation":
        loaded = next(iter(Parent.find(parent.id).children))
    else:
        loaded = next(iter(Parent.includes("children"))).children
        loaded = next(iter(loaded))
    assert loaded.id == child.id
    assert events == [("find", "child"), ("initialize", "child")]


def test_empty_queries_return_empty_results_and_find_reports_missing_records(family):
    _, Child, _ = family
    query = Child.all()
    assert isinstance(query, ModelQuery)
    assert list(query) == list(query.all()) == query.__json__() == []
    assert query.first() is query.last() is Child.find_by(name="absent") is None
    assert query.count() == 0
    with pytest.raises(RecordNotFoundException, match="Child record with id 99"):
        Child.find(99)


def test_query_chaining_preserves_original_scope_and_serializes_ordered_results(
    family, session, mocker
):
    Parent, Child, events = family
    parent = Parent.create(name="parent")
    Child.create(name="first", parent=parent)
    query = Child.where(Child.parent_id == parent.id)
    filtered = query.where(name="second").order(id="desc").limit(1).offset(0)
    assert filtered is not query
    execute = mocker.spy(session, "execute")
    assert isinstance(filtered.to_sql(), str)
    execute.assert_not_called()
    Child.create(name="second", parent=parent)
    events.clear()
    assert filtered.__json__() == [{"label": "second"}]
    assert [entry.name for entry in filtered] == ["second"]
    assert [entry.name for entry in query] == ["first", "second"]


def test_all_preserves_scope_identity_and_defers_execution(family, session, mocker):
    Parent, Child, _ = family
    parent = Parent.create(name="parent")
    Child.create(name="first", parent=parent)
    second = Child.create(name="second", parent=parent)
    second_id = second.id
    session.expunge_all()
    execute = mocker.spy(session, "execute")

    query = Child.all()
    original_sql = query.to_sql()
    scope = (
        query.where(Child.name.in_(["first", "second"]))
        .includes("parent")
        .order(name="desc")
        .limit(1)
        .offset(0)
    )
    assert isinstance(query, ModelQuery)
    assert query.all() is query
    assert scope.all().all() is scope
    assert query.to_sql() == original_sql
    execute.assert_not_called()

    records = list(scope.all())
    assert [record.id for record in records] == [second_id]
    assert execute.call_count == 2
    assert records[0].parent.name == "parent"
    assert execute.call_count == 2


@pytest.mark.parametrize("consumer", ["iteration", "list", "repr", "json", "last"])
def test_query_consumers_execute_once(family, session, mocker, consumer):
    Parent, Child, _ = family
    parent = Parent.create(name="parent")
    Child.create(name="first", parent=parent)
    second = Child.create(name="second", parent=parent)
    query = Child.order(id="asc").limit(1).offset(1).all()
    expected_repr = repr([second])
    execute = mocker.spy(session, "execute")

    if consumer == "iteration":
        assert [record for record in query] == [second]
    elif consumer == "list":
        assert list(query) == [second]
    elif consumer == "repr":
        assert repr(query) == expected_repr
    elif consumer == "json":
        assert query.__json__() == [{"label": "second"}]
    else:
        assert query.last() is second

    execute.assert_called_once()


@pytest.mark.parametrize("direction, expected", [("asc", "Zulu"), ("desc", "Alpha")])
def test_unpaginated_last_loads_only_the_last_record(
    family, session, direction, expected
):
    _, Child, events = family
    for name in ("Middle", "Zulu", "Alpha"):
        Child.create(name=name)
    session.expunge_all()
    events.clear()
    assert Child.order(name=direction).last().name == expected
    assert events == [("find", expected), ("initialize", expected)]


@pytest.mark.parametrize(
    "nulls, expected", [("first", "Related"), ("last", "Unrelated")]
)
def test_last_reverses_explicit_null_ordering(family, nulls, expected):
    Parent, Child, _ = family
    parent = Parent.create(name="Parent")
    Child.create(name="Related", parent=parent)
    Child.create(name="Unrelated")
    ordering = Child.parent_id.asc()
    ordering = ordering.nulls_first() if nulls == "first" else ordering.nulls_last()
    assert Child.order(ordering).last().name == expected


def test_last_honors_native_statement_ordering_and_pagination(family):
    _, Child, _ = family
    for name in ("Alpha", "Middle", "Zulu"):
        Child.create(name=name)
    query = Child.all()
    query.statement = query.statement.order_by(None).order_by(Child.name.desc())
    assert query.last().name == "Alpha"
    query.statement = query.statement.limit(2)
    assert query.last().name == "Middle"
    assert query.offset(1).last().name == "Alpha"


def test_all_scopes_reflect_new_records_on_reuse(family, session, mocker):
    Parent, Child, _ = family
    parent = Parent.create(name="parent")
    first = Child.create(name="first", parent=parent)
    query = Child.where(parent=parent).order(id="asc").all()
    assert list(query) == [first]
    second = Child.create(name="second", parent=parent)
    execute = mocker.spy(session, "execute")

    scope = query.all()
    limited = scope.limit(1).all()
    execute.assert_not_called()
    assert list(limited) == [first]
    assert list(scope) == [first, second]
    assert list(query) == [first, second]
