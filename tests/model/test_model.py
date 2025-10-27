import pytest
from datetime import datetime
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime
from flaskteroids.model import Model, validates
from flaskteroids.rules import rules


@pytest.fixture(autouse=True)
def init(init_models):
    init_models(Base, [
        (UserBase, User),
    ])


Base = declarative_base()


class UserBase(Base):
    __tablename__ = 'users'

    id = Column(Integer(), primary_key=True, autoincrement=True)
    username = Column(String())
    age = Column(Integer())
    last_login = Column(DateTime())


@rules(
    validates('username', presence=True),
)
class User(Model):
    pass


def test_new():
    user = User.new(username='one')
    assert user.username == 'one'


def test_create():
    user = User.create(username='one')
    assert user.id


def test_edit():
    user = User.create(username='one')
    user.username = 'two'
    user.save()

    user = User.find(id=user.id)
    assert user.username == 'two'


def test_save():
    user = User.new(username='one')
    assert user.save()


def test_save_with_errors():
    user = User.new()
    assert not user.save()
    assert user.errors
    assert user.errors.count == 1


def test_find():
    user = User.create(username='one')
    assert User.find(id=user.id)


def test_all():
    User.create(username='one')
    User.create(username='two')
    User.create(username='three')
    assert len(list(User.all())) == 3


def test_find_by():
    User.create(username='one')
    User.create(username='two')
    User.create(username='three')
    one = User.find_by(username='one')
    assert one
    assert one.username == 'one'


@pytest.mark.parametrize('query_factory, expected_count', [
    (lambda: User.username == 'one', 1),
    (lambda: User.username == 'two', 1),
    (lambda: User.username.in_(['one', 'three']), 2),
    (lambda: User.age >= 25, 2),
    (lambda: User.last_login < datetime(2021, 1, 1), 1),
    (lambda: (User.age < 30) & (User.last_login >= datetime(2021, 1, 1)), 1),
])
def test_where(query_factory, expected_count):
    User.create(username='one', age=30, last_login=datetime(2022, 5, 20))
    User.create(username='two', age=25, last_login=datetime(2021, 6, 15))
    User.create(username='three', age=15, last_login=datetime(2020, 1, 1))
    query = query_factory()
    users = User.where(query).all()
    assert len(list(users)) == expected_count
