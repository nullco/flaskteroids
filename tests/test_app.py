import re
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


def test_users_create(client):
    res = client.get('/users/new/')
    csrf_token = _extract_csrf_token(res)
    res = client.post('/users/', data={
        'csrf_token': csrf_token,
        'user.username': 'test'
    })
    assert res.status_code == HTTPStatus.FOUND


def test_users_update(client):
    res = client.get('/users/new/')
    csrf_token = _extract_csrf_token(res)
    res = client.post('/users/', data={
        'csrf_token': csrf_token,
        'user.username': 'test'
    })
    location = res.location
    res = client.get(f'{location}edit')
    csrf_token = _extract_csrf_token(res)
    res = client.put(location, data={
        'csrf_token': csrf_token,
        'user.username': 'updated'
    })
    assert res.status_code == HTTPStatus.FOUND


def _extract_csrf_token(res):
    match = re.search(r'name="csrf_token" value="([^"]+)"', res.text)
    if not match:
        return ""
    return match.group(1)
