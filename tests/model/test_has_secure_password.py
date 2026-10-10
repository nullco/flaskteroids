import pytest
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

from flaskteroids.model import (
    Model,
    PasswordAuthenticator,
    RecordNotFoundException,
    has_secure_password,
)
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
class User(Model, PasswordAuthenticator):
    pass


@pytest.fixture
def user_params():
    return {
        'email_address': 'john-doe@example.org',
        'password': 'Abcde12345$',
    }


@pytest.fixture
def new_user(user_params):
    return User.new(**user_params)


@pytest.fixture
def existing_user(user_params):
    return User.create(**user_params)


@pytest.fixture
def reset_serializer():
    return URLSafeTimedSerializer('test', salt=f'pwres:{User.__module__}.{User.__qualname__}:password')


def test_authenticate_by(existing_user):
    user = User.authenticate_by(email_address=existing_user.email_address, password=existing_user.password)
    assert user
    assert user.email_address == existing_user.email_address
    assert user.password_digest != existing_user.password


def test_authenticate_by_with_wrong_password(existing_user):
    user = User.authenticate_by(email_address=existing_user.email_address, password='Wro000nggg$')
    assert not user


def test_authenticate(existing_user):
    assert existing_user.authenticate('Abcde12345$')


def test_authenticate_with_wrong_password(existing_user):
    assert not existing_user.authenticate('Wro00nggg$')


def test_password_with_confirmation(new_user):
    new_user.password_confirmation = 'wrong'
    assert not new_user.save()
    assert new_user.errors
    new_user.password_confirmation = new_user.password
    assert new_user.save()


def test_change_password(existing_user):
    password_digest = existing_user.password_digest
    existing_user.password = 'N3wP4$$'
    assert existing_user.save()
    assert not existing_user.errors
    assert existing_user.password_digest != password_digest


def test_change_password_with_confirmation(existing_user):
    password_digest = existing_user.password_digest
    existing_user.password = 'N3wP4$$'
    existing_user.password_confirmation = 'N3wP4$$'
    assert existing_user.save()
    assert not existing_user.errors
    assert existing_user.password_digest != password_digest


def test_change_password_via_update(existing_user):
    password_digest = existing_user.password_digest
    assert existing_user.update(password='N3wP4$$')
    assert not existing_user.errors
    assert existing_user.password_digest != password_digest


def test_change_password_with_confirmation_via_update(existing_user):
    password_digest = existing_user.password_digest
    assert existing_user.update(password='N3wP4$$', password_confirmation='N3wP4$$')
    assert not existing_user.errors
    assert existing_user.password_digest != password_digest


def test_change_password_with_wrong_confirmation_via_update(existing_user):
    assert not existing_user.update(password='N3wP4$$', password_confirmation='Wrong')
    assert existing_user.errors


def test_change_empty_password(existing_user):
    existing_user.password = ''
    assert not existing_user.save()
    assert existing_user.errors


def test_password_reset_token(existing_user):
    token = existing_user.password_reset_token
    user = User.find_by_password_reset_token(token)
    assert user.id == existing_user.id


@pytest.mark.parametrize('age, expired', [(900, False), (901, True)])
def test_password_reset_token_expiration(existing_user, mocker, age, expired):
    clock = mocker.patch('itsdangerous.timed.time.time', return_value=1000)
    token = existing_user.password_reset_token
    clock.return_value += age

    if expired:
        with pytest.raises(SignatureExpired):
            User.find_by_password_reset_token(token)
    else:
        assert User.find_by_password_reset_token(token).id == existing_user.id


@pytest.mark.parametrize('password', ['N3wP4$$', 'Abcde12345$'])
def test_password_change_invalidates_reset_token(existing_user, password):
    token = existing_user.password_reset_token
    user = User.find_by_password_reset_token(token)

    assert user.update(password=password)

    with pytest.raises(BadSignature):
        User.find_by_password_reset_token(token)
    new_token = existing_user.password_reset_token
    assert new_token != token
    assert User.find_by_password_reset_token(new_token).id == existing_user.id


def test_password_reset_token_refreshes_timestamp(existing_user, mocker):
    clock = mocker.patch('itsdangerous.timed.time.time', return_value=1000)
    token = existing_user.password_reset_token
    clock.return_value += 901
    new_token = existing_user.password_reset_token

    assert new_token != token
    assert User.find_by_password_reset_token(new_token).id == existing_user.id
    with pytest.raises(SignatureExpired):
        User.find_by_password_reset_token(token)


def test_failed_password_change_does_not_invalidate_reset_token(existing_user):
    token = existing_user.password_reset_token

    assert not existing_user.update(password='N3wP4$$', password_confirmation='Wrong')

    assert User.find_by_password_reset_token(token).id == existing_user.id


def test_non_password_change_does_not_invalidate_reset_token(existing_user):
    token = existing_user.password_reset_token

    assert existing_user.update(email_address='new-address@example.org')

    assert User.find_by_password_reset_token(token).id == existing_user.id


def test_password_reset_token_rejects_tampering(existing_user):
    token = existing_user.password_reset_token

    with pytest.raises(BadSignature):
        User.find_by_password_reset_token(token + '.tampered')


def test_password_reset_token_rejects_legacy_payload(existing_user):
    token = URLSafeTimedSerializer('test').dumps(existing_user.id, salt='pwres')

    with pytest.raises(BadSignature):
        User.find_by_password_reset_token(token)


def test_password_reset_token_payload_hides_password_digest(existing_user, reset_serializer):
    payload = reset_serializer.loads(existing_user.password_reset_token)

    assert payload['id'] == existing_user.id
    assert len(payload['fingerprint']) == 64
    assert existing_user.password_digest not in str(payload)
    assert existing_user.password not in str(payload)


@pytest.mark.parametrize('payload', [
    None, 123, [], {},
    {'id': None, 'fingerprint': 'invalid'},
    {'id': True, 'fingerprint': 'invalid'},
    {'id': 1, 'fingerprint': None},
    {'id': 1, 'fingerprint': '\u2603'},
    {'id': 1, 'fingerprint': 'invalid'},
])
def test_password_reset_token_rejects_signed_unexpected_payload(existing_user, reset_serializer, payload):
    token = reset_serializer.dumps(payload)

    with pytest.raises(BadSignature):
        User.find_by_password_reset_token(token)


def test_password_change_invalidates_all_outstanding_reset_tokens(existing_user, mocker):
    clock = mocker.patch('itsdangerous.timed.time.time', return_value=1000)
    first_token = existing_user.password_reset_token
    clock.return_value += 1
    second_token = existing_user.password_reset_token

    assert existing_user.update(password='N3wP4$$')

    for token in [first_token, second_token]:
        with pytest.raises(BadSignature):
            User.find_by_password_reset_token(token)


def test_password_reset_token_rejects_wrong_secret_key(existing_user, current_app):
    token = existing_user.password_reset_token
    current_app.config['SECRET_KEY'] = 'other-secret'

    with pytest.raises(BadSignature):
        User.find_by_password_reset_token(token)


def test_password_reset_token_for_deleted_user(existing_user):
    token = existing_user.password_reset_token
    assert existing_user.destroy()

    with pytest.raises(RecordNotFoundException):
        User.find_by_password_reset_token(token)


def test_password_reset_token_is_scoped_to_model(existing_user, init_models):
    @rules(has_secure_password())
    class OtherUser(Model, PasswordAuthenticator):
        pass

    init_models(Base, [(UserBase, User), (UserBase, OtherUser)])
    token = existing_user.password_reset_token

    with pytest.raises(BadSignature):
        OtherUser.find_by_password_reset_token(token)
    other_token = OtherUser.find(existing_user.id).password_reset_token
    assert OtherUser.find_by_password_reset_token(other_token).id == existing_user.id


def test_password_reset_token_with_custom_password_field(init_models):
    class PasscodeUserBase(Base):
        __tablename__ = 'passcode_users'

        id = Column(Integer(), primary_key=True, autoincrement=True)
        passcode_digest = Column(String(), nullable=False)

    @rules(has_secure_password('passcode'))
    class PasscodeUser(Model, PasswordAuthenticator):
        pass

    init_models(Base, [(PasscodeUserBase, PasscodeUser)])
    user = PasscodeUser.create(passcode='Abcde12345$')
    token = user.passcode_reset_token

    assert PasscodeUser.find_by_password_reset_token(token).id == user.id
    assert user.update(passcode='N3wP4$$')
    with pytest.raises(BadSignature):
        PasscodeUser.find_by_password_reset_token(token)
    assert PasscodeUser.find_by_password_reset_token(user.passcode_reset_token).id == user.id
