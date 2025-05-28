import pytest
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String
from flaskteroids.model import Model, has_secure_password
from flaskteroids.rules import rules


@pytest.fixture(autouse=True)
def init(init_models):
    init_models(Base, [(UserBase, User)])


Base = declarative_base()


class UserBase(Base):
    __tablename__ = 'users'

    id = Column(Integer(), primary_key=True, autoincrement=True)
    email_address = Column(String(), nullable=False)
    password_digest = Column(String(), nullable=False)


@rules(
    has_secure_password()
)
class User(Model):
    pass


@pytest.fixture
def user_params():
    return {
        'email_address': 'john-doe@example.org',
        'password': 'Abcde12345$',
        'password_confirmation': 'Abcde12345$'
    }


@pytest.fixture
def new_user(user_params):
    return User.new(**user_params)


@pytest.fixture
def existing_user(user_params):
    return User.create(**user_params)


def test_authenticate_by(existing_user):
    user = User.authenticate_by(email_address=existing_user.email_address, password=existing_user.password)
    assert user.email_address == existing_user.email_address
    assert user.password_digest != existing_user.password


def test_authenticate(existing_user):
    assert existing_user.authenticate('Abcde12345$')

def test_authenticate_fails(existing_user):
    assert not existing_user.authenticate('Wro00nggg$')


def test_password_confirmation(new_user):
    new_user.password_confirmation = 'wrong'
    assert not new_user.save()
    assert new_user.errors


def test_change_password(existing_user):
    password_digest = existing_user.password_digest
    existing_user.password = 'N3wP4$$'
    assert not existing_user.save()
    existing_user.password_confirmation = 'N3wP4$$'
    existing_user.save()
    assert not existing_user.errors
    assert existing_user.password_digest != password_digest


def test_change_empty_password(existing_user):
    existing_user.password = ''
    assert not existing_user.save()
    assert existing_user.errors
