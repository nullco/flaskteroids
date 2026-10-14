import pytest
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base

from flaskteroids.model import (
    Model,
    ModelQuery,
    RecordNotFoundException,
    Relation,
    after_find,
    after_initialize,
    belongs_to,
    has_many,
    init,
    validates,
)
from flaskteroids.rules import rules

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

    @rules(has_many("children", dependent="destroy"))
    class Parent(Model):
        pass

    @rules(
        belongs_to("parent"),
        validates("name", presence=True),
        after_initialize("_initialized"),
        after_find("_found"),
    )
    class Child(Model):
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


def test_relation_creation_validation_inverse_and_cascade(family):
    Parent, Child, _ = family
    parent = Parent.create(name="parent")
    assert isinstance(parent.children, Relation)
    invalid = parent.children.create()
    assert invalid.is_new_record()
    assert invalid.errors.full_messages() == ["Field name is blank"]
    assert len(parent.children) == Child.count() == 0
    child = parent.children.create(name="child")
    assert child.is_persisted()
    assert child.parent.id == parent.id
    assert [entry.id for entry in parent.children] == [child.id]
    parent.destroy()
    assert Child.count() == 0


def test_fk_validation_is_registered_once_and_rejects_unsaved_target(family):
    Parent, Child, _ = family
    init(Child)
    init(Child)
    child = Child.new(name="child", parent=Parent.new(name="unsaved"))
    assert child.save() is False
    assert child.errors.full_messages() == ["parent must exist"]


@pytest.mark.parametrize("load", ["find", "query", "relation", "includes"])
def test_loaded_record_callbacks_do_not_replay_constructor(family, load):
    Parent, Child, events = family
    parent = Parent.create(name="parent")
    child = Child.create(name="child", parent=parent)
    events.clear()
    if load == "find":
        loaded = Child.find(child.id)
    elif load == "query":
        loaded = next(Child.all().all())
    elif load == "relation":
        loaded = next(iter(parent.children))
    else:
        loaded = next(iter(Parent.includes("children"))).children
        loaded = next(iter(loaded))
    assert loaded.id == child.id
    assert events == [("initialize", "child"), ("find", "child")]


def test_empty_queries_and_record_errors(family):
    _, Child, _ = family
    query = Child.all()
    assert isinstance(query, ModelQuery)
    assert list(query) == list(query.all()) == query.__json__() == []
    assert query.first() is query.last() is Child.find_by(name="absent") is None
    assert query.count() == 0
    with pytest.raises(RecordNotFoundException, match="Child record with id 99"):
        Child.find(99)


def test_query_mutability_laziness_order_and_serializer(family, session, mocker):
    Parent, Child, events = family
    parent = Parent.create(name="parent")
    Child.create(name="first", parent=parent)
    query = Child.where(Child.parent_id == parent.id)
    assert query.where(name="second") is query
    assert query.order(id="desc").limit(1).offset(0) is query
    execute = mocker.spy(session, "execute")
    sql = query.to_sql()
    assert "children.name = 'second'" in sql
    assert "ORDER BY children.id DESC" in sql
    execute.assert_not_called()
    Child.create(name="second", parent=parent)
    events.clear()
    assert query.__json__() == [{"label": "second"}]
    assert [entry.name for entry in query] == ["second"]
