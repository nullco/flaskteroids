import pytest
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String
from flaskteroids.model import Model, validates
from flaskteroids.rules import rules


@pytest.fixture(autouse=True)
def init(init_models):
    init_models(Base, [(UserBase, User)])


Base = declarative_base()


class UserBase(Base):
    __tablename__ = 'users'

    id = Column(Integer(), primary_key=True, autoincrement=True)
    username = Column(String())


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
