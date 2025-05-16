import pytest
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, ForeignKey, Integer, String, create_engine
from flaskteroids import model
from flaskteroids.model import Model, validates, belongs_to, has_many
import flaskteroids.registry as registry
from flaskteroids.rules import rules


@pytest.fixture
def engine():
    return create_engine('sqlite:///:memory:')


@pytest.fixture(autouse=True)
def session(mocker, engine):
    Session = sessionmaker(bind=engine)
    return mocker.patch.object(model, 'session', return_value=Session())


@pytest.fixture(autouse=True)
def init_models(engine):
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

    Base.metadata.create_all(engine)
    registry.get(model.Model)['models'] = {'User': User, 'Group': Group}
    registry.get(User)['base_class'] = UserBase
    registry.get(Group)['base_class'] = GroupBase
    model.init(User)
    model.init(Group)


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
