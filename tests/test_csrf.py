from types import SimpleNamespace

import pytest
from flask import Flask
from itsdangerous import URLSafeTimedSerializer

from flaskteroids.csrf import CSRFToken


@pytest.fixture
def csrf():
    return CSRFToken(secret_key='test-secret-key')


@pytest.fixture
def flask_app(csrf):
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.before_request(csrf.validate)

    @app.get('/token')
    def token():
        return csrf.generate()

    @app.route('/protected', methods=['GET', 'HEAD', 'OPTIONS', 'TRACE', 'POST', 'PUT', 'PATCH', 'DELETE'])
    def protected():
        return '', 204

    return app


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()


@pytest.fixture
def token(client):
    return client.get('/token').get_data(as_text=True)


def test_generate_returns_string(token):
    assert isinstance(token, str)
    assert token


def test_generate_reuses_session_nonce(client, token):
    with client.session_transaction() as browser_session:
        nonce = browser_session['csrf_nonce']
    second_token = client.get('/token').get_data(as_text=True)
    serializer = URLSafeTimedSerializer('test-secret-key')

    assert serializer.loads(token, salt='csrf-token') == nonce
    assert serializer.loads(second_token, salt='csrf-token') == nonce
    assert client.post('/protected', data={'csrf_token': token}).status_code == 204
    assert client.post('/protected', data={'csrf_token': second_token}).status_code == 204


def test_generate_with_different_secret_keys(flask_app):
    with flask_app.test_request_context():
        token1 = CSRFToken(secret_key='key1').generate()
        token2 = CSRFToken(secret_key='key2').generate()

    assert token1 != token2


@pytest.mark.parametrize('method', ['GET', 'HEAD', 'OPTIONS', 'TRACE'])
def test_validate_skips_methods(client, method):
    assert client.open('/protected', method=method).status_code == 204


@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE'])
def test_validate_checks_methods(client, method):
    response = client.open('/protected', method=method)

    assert response.status_code == 400
    assert 'Missing CSRF token.' in response.get_data(as_text=True)


@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE'])
@pytest.mark.parametrize('transport', ['form', 'header'])
def test_validate_accepts_session_token(client, token, method, transport):
    kwargs = {'data': {'csrf_token': token}} if transport == 'form' else {'headers': {'X-CSRF-TOKEN': token}}

    assert client.open('/protected', method=method, **kwargs).status_code == 204


def test_validate_prefers_form_over_header(client, token):
    response = client.post('/protected', data={'csrf_token': token}, headers={'X-CSRF-TOKEN': 'invalid'})

    assert response.status_code == 204


def test_validate_rejects_invalid_form_despite_valid_header(client, token):
    response = client.post('/protected', data={'csrf_token': 'invalid'}, headers={'X-CSRF-TOKEN': token})

    assert response.status_code == 400


def test_validate_aborts_on_invalid_token(client, token):
    response = client.post('/protected', data={'csrf_token': token + '.tampered'})

    assert response.status_code == 400
    assert 'Invalid CSRF token.' in response.get_data(as_text=True)


def test_validate_rejects_wrong_signing_key(client, token):
    with client.session_transaction() as browser_session:
        nonce = browser_session['csrf_nonce']
    invalid_token = URLSafeTimedSerializer('wrong-secret-key').dumps(nonce, salt='csrf-token')

    assert client.post('/protected', data={'csrf_token': invalid_token}).status_code == 400


def test_validate_rejects_signed_malformed_payload(client, token):
    serializer = URLSafeTimedSerializer('test-secret-key')
    invalid_token = serializer.make_signer('csrf-token').sign(b'bm90LWpzb24').decode()

    assert client.post('/protected', data={'csrf_token': invalid_token}).status_code == 400


@pytest.mark.parametrize('age, expected_status', [(3600, 204), (3601, 400)])
def test_validate_checks_expiration(client, mocker, age, expected_status):
    clock = mocker.patch('itsdangerous.timed.time.time', return_value=1000)
    token = client.get('/token').get_data(as_text=True)
    clock.return_value += age

    response = client.post('/protected', data={'csrf_token': token})

    assert response.status_code == expected_status
    if expected_status == 400:
        assert 'CSRF token has expired.' in response.get_data(as_text=True)


@pytest.mark.parametrize('transport', ['form', 'header'])
def test_validate_rejects_token_from_another_session(flask_app, client, token, transport):
    other_client = flask_app.test_client()
    other_token = other_client.get('/token').get_data(as_text=True)
    kwargs = {'data': {'csrf_token': token}} if transport == 'form' else {'headers': {'X-CSRF-TOKEN': token}}

    response = other_client.post('/protected', **kwargs)

    assert response.status_code == 400
    assert token != other_token
    assert 'CSRF token does not match this session.' in response.get_data(as_text=True)
    assert other_client.post('/protected', data={'csrf_token': other_token}).status_code == 204
    assert client.post('/protected', data={'csrf_token': token}).status_code == 204


def test_validate_rejects_token_without_session(flask_app, token):
    other_client = flask_app.test_client()

    assert other_client.post('/protected', data={'csrf_token': token}).status_code == 400
    with other_client.session_transaction() as browser_session:
        assert 'csrf_nonce' not in browser_session


def test_validate_rejects_token_after_session_is_cleared(client, token):
    with client.session_transaction() as browser_session:
        browser_session.clear()

    assert client.post('/protected', data={'csrf_token': token}).status_code == 400
    new_token = client.get('/token').get_data(as_text=True)
    assert new_token != token
    assert client.post('/protected', data={'csrf_token': token}).status_code == 400
    assert client.post('/protected', data={'csrf_token': new_token}).status_code == 204


@pytest.mark.parametrize('payload', ['csrf-token', 'different-nonce', None, 123, [], {}, '\u2603'])
def test_validate_rejects_signed_unexpected_payload(client, token, payload):
    invalid_token = URLSafeTimedSerializer('test-secret-key').dumps(payload, salt='csrf-token')

    assert client.post('/protected', data={'csrf_token': invalid_token}).status_code == 400


@pytest.mark.parametrize('nonce', [None, '', 123, []])
def test_validate_rejects_invalid_session_nonce(client, token, nonce):
    with client.session_transaction() as browser_session:
        browser_session['csrf_nonce'] = nonce

    assert client.post('/protected', data={'csrf_token': token}).status_code == 400


def test_validate_can_be_disabled(flask_app, client):
    flask_app.config.action_controller = SimpleNamespace(allow_forgery_protection=False)

    assert client.post('/protected').status_code == 204


@pytest.mark.parametrize('secret_key', ['', None])
def test_generate_with_empty_secret_key(flask_app, secret_key):
    with flask_app.test_request_context():
        token = CSRFToken(secret_key=secret_key).generate()

    assert isinstance(token, str)
    assert token
