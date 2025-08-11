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
    group_id = Column(Integer(), ForeignKey('groups.id'), nullable=False)


class GroupBase(Base):
    __tablename__ = 'groups'

    id = Column(Integer(), primary_key=True, autoincrement=True)
    name = Column(String())


@rules(
    validates('username'),
    belongs_to('group')
)
class User(Model):
    pass


@rules(
    has_many('users', dependent='destroy')
)
class Group(model.Model):
    pass


def test_create():
    group = Group.create(name='one')
    user = User.create(username='one', group=group)
    assert user.id


def test_edit():
    group = Group.create(name='one')
    user = User.create(username='one', group=group)
    user.username = 'two'
    user.save()

    user = User.find(id=user.id)
    assert user.username == 'two'


def test_save():
    group = Group.create(name='one')
    user = User.new(username='one', group=group)
    assert user.save()


def test_find():
    group = Group.create(name='one')
    user = User.create(username='one', group=group)
    assert User.find(id=user.id)


def test_belongs_to():
    group = Group.create(name='one')
    user = User.create(username='one', group=group)
    assert user.group.id == group.id


def test_has_many():
    group = Group.create(name='one')
    User.create(username='one', group=group)
    User.create(username='two', group=group)
    User.create(username='three', group=group)
    assert len(group.users) == 3
    assert len([u for u in User.all()]) == 3


def test_destroy():
    group = Group.create(name='one')
    User.create(username='one', group=group)
    User.create(username='two', group=group)
    assert len(group.users) == 2
    assert len([u for u in User.all()]) == 2
    group.destroy()
    assert len([u for u in User.all()]) == 0
