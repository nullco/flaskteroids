import pytest
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, ForeignKey, Integer, String
from flaskteroids import model
from flaskteroids.model import Model, validates, belongs_to, has_many
from flaskteroids.rules import rules


@pytest.fixture(autouse=True)
def init(init_models):
    init_models(Base, [(UserBase, User), (GroupBase, Group)])


Base = declarative_base()


class UserBase(Base):
    __tablename__ = 'users'

    id = Column(Integer(), primary_key=True, autoincrement=True)
    username = Column(String())
    group_id = Column(Integer(), ForeignKey('groups.id'))


class GroupBase(Base):
    __tablename__ = 'groups'

    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())


@rules(
    validates('username', presence=True),
    belongs_to('group')
)
class User(Model):
    pass


@rules(
    has_many('users')
)
class Group(model.Model):
    pass


def test_new():
    user = User.new(username='one')
    assert user.username == 'one'


def test_create():
    user = User.create(username='one')
    assert user.id


def test_save():
    user = User.new(username='one')
    assert user.save()


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
