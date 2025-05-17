from http import HTTPStatus


def test_healthcheck(client):
    res = client.get('/up/')
    assert res.status_code == HTTPStatus.OK


def test_default_root(client):
    res = client.get('/')
    assert res.status_code == HTTPStatus.OK
    assert b'Flaskteroids' in res.data
    assert b'Version' in res.data


def test_users_index(client):
    res = client.get('/users/')
    assert res.status_code == HTTPStatus.OK
