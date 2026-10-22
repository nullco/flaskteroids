import pytest
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base

from flaskteroids.model import validates
from tests.model.schema_support import model_base


@pytest.fixture(autouse=True)
def init(init_models):
    init_models(Base, [(UserBase, User), (GroupBase, Group)])


Base = declarative_base()


class UserBase(Base):
    __tablename__ = "users"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    username = Column(String())
    group_id = Column(Integer(), ForeignKey("groups.id"), nullable=False)


class GroupBase(Base):
    __tablename__ = "groups"

    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())


ApplicationModel = model_base(
    Base,
    relationships={
        "User": {"group": {"argument": "Group", "back_populates": "users"}},
        "Group": {
            "users": {
                "argument": "User",
                "back_populates": "group",
                "cascade": "all, delete-orphan",
            }
        },
    },
)


class User(ApplicationModel):
    validates("username")


class Group(ApplicationModel):
    pass


def test_belongs_to_returns_associated_parent():
    group = Group.create(name="one")
    user = User.create(username="one", group=group)
    assert user.group.id == group.id


def test_has_many_returns_associated_children():
    group = Group.create(name="one")
    User.create(username="one", group=group)
    User.create(username="two", group=group)
    User.create(username="three", group=group)
    assert len(group.users) == 3
    assert len([u for u in User.all()]) == 3


def test_destroy_cascades_to_associated_children():
    group = Group.create(name="one")
    User.create(username="one", group=group)
    User.create(username="two", group=group)
    assert len(group.users) == 2
    assert len([u for u in User.all()]) == 2
    group.destroy()
    assert len([u for u in User.all()]) == 0


@pytest.fixture
def user_groups():
    group_one = Group.create(name="one")
    User.create(username="one", group=group_one)
    User.create(username="two", group=group_one)
    group_two = Group.create(name="two")
    User.create(username="three", group=group_two)
    User.create(username="four", group=group_two)


@pytest.mark.usefixtures("user_groups")
@pytest.mark.parametrize("eager, expected_queries", [(False, 3), (True, 2)])
def test_collection_loading_batches_queries_with_includes(
    engine, eager, expected_queries
):
    def capture():
        groups = Group.includes("users") if eager else Group.all()
        return [user for group in groups for user in group.users]

    captured_statements = capture_statements(engine, capture)
    assert len(captured_statements) == expected_queries


@pytest.mark.usefixtures("user_groups")
@pytest.mark.parametrize("eager, expected_queries", [(False, 3), (True, 2)])
def test_parent_loading_batches_queries_with_includes(
    engine, session, eager, expected_queries
):
    session.expunge_all()

    def capture():
        users = User.includes("group") if eager else User.all()
        return [user.group for user in users]

    captured_statements = capture_statements(engine, capture)
    assert len(captured_statements) == expected_queries


def capture_statements(engine, func):
    from sqlalchemy import event

    captured_statements = []

    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        captured_statements.append(statement)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        func()
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
    return captured_statements
