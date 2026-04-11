import pytest
from flask import Flask
from flaskteroids.csrf import CSRFToken
from werkzeug.exceptions import BadRequest


@pytest.fixture
def csrf():
    return CSRFToken(secret_key='test-secret-key')


@pytest.fixture
def flask_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret-key'
    return app


def test_generate_returns_string(csrf):
    token = csrf.generate()
    assert isinstance(token, str)
    assert len(token) > 0


def test_generate_with_different_secret_keys():
    csrf1 = CSRFToken(secret_key='key1')
    csrf2 = CSRFToken(secret_key='key2')
    token1 = csrf1.generate()
    token2 = csrf2.generate()
    assert token1 != token2


@pytest.mark.parametrize('method', ['GET', 'HEAD', 'OPTIONS', 'TRACE'])
def test_validate_skips_methods(csrf, flask_app, method):
    with flask_app.test_request_context('/', method=method):
        csrf.validate()


@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE'])
def test_validate_checks_methods(csrf, flask_app, method):
    with flask_app.test_request_context('/', method=method):
        with pytest.raises(BadRequest):
            csrf.validate()


def test_validate_aborts_on_missing_token(csrf, flask_app):
    with flask_app.test_request_context('/', method='POST'):
        with pytest.raises(BadRequest):
            csrf.validate()


def test_validate_accepts_token_from_form(csrf, flask_app):
    token = csrf.generate()
    with flask_app.test_request_context('/', method='POST', data={'csrf_token': token}):
        csrf.validate()


def test_validate_accepts_token_from_header(csrf, flask_app):
    token = csrf.generate()
    with flask_app.test_request_context('/', method='POST', headers={'X-CSRF-TOKEN': token}):
        csrf.validate()


def test_validate_prefers_form_over_header(csrf, flask_app):
    valid_token = csrf.generate()
    invalid_token = 'invalid'
    with flask_app.test_request_context(
        '/',
        method='POST',
        data={'csrf_token': valid_token},
        headers={'X-CSRF-TOKEN': invalid_token}
    ):
        csrf.validate()


def test_validate_aborts_on_invalid_token(csrf, flask_app):
    with flask_app.test_request_context('/', method='POST', data={'csrf_token': 'invalid'}):
        with pytest.raises(BadRequest):
            csrf.validate()


def test_validate_aborts_on_expired_token(csrf, flask_app, mocker):
    from itsdangerous import SignatureExpired
    mocker.patch.object(csrf._serializer, 'loads', side_effect=SignatureExpired('expired'))
    with flask_app.test_request_context('/', method='POST', data={'csrf_token': 'some-token'}):
        with pytest.raises(BadRequest):
            csrf.validate()


def test_csrf_with_empty_secret_key():
    csrf = CSRFToken(secret_key='')
    token = csrf.generate()
    assert isinstance(token, str)


def test_csrf_with_none_secret_key():
    csrf = CSRFToken(secret_key=None)
    token = csrf.generate()
    assert isinstance(token, str)
