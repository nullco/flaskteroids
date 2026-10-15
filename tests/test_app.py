import re
from http import HTTPStatus

import pytest

from flaskteroids import __version__
from flaskteroids.application import Application
from flaskteroids.controller import render
from flaskteroids.exceptions import (
    InvalidParameter,
    MissingParameter,
    ProgrammerError,
    UserError,
)


def test_broken_models_package_stops_setup(discovery_package, tmp_path):
    name = discovery_package({"__init__.py": "import phase4_missing_driver"})

    class BrokenApplication(Application):
        def configure(self, config):
            config.paths.models = name

        def _configure_database(self):
            self.database_url = "sqlite:///:memory:"

    with pytest.raises(ModuleNotFoundError) as raised:
        BrokenApplication.initialize(environment="test", root_path=tmp_path)
    assert raised.value.name == "phase4_missing_driver"


def test_healthcheck(client):
    res = client.get("/up/")
    assert res.status_code == HTTPStatus.OK


def test_default_root(client):
    res = client.get("/")
    assert res.status_code == HTTPStatus.OK
    assert b"Flaskteroids" in res.data
    assert f"v{__version__}" in res.get_data(as_text=True)


def test_users_index(client):
    res = client.get("/users/")
    assert res.status_code == HTTPStatus.OK


def test_users_create(client):
    res = client.get("/users/new/")
    csrf_token = _extract_csrf_token(res)
    res = client.post(
        "/users/", data={"csrf_token": csrf_token, "user.username": "test"}
    )
    assert res.status_code == HTTPStatus.FOUND


@pytest.mark.parametrize("accept", ["text/html", "application/json"])
@pytest.mark.parametrize(
    "data, message",
    [
        ({}, "Parameter is missing or empty"),
        ({"user.admin": "true"}, "Parameter is missing or empty"),
        ({"user": "wrong"}, "Invalid parameter type. Not a dict"),
        ({"user.username.name": "wrong"}, "Invalid parameter type. Not a scalar"),
    ],
)
def test_parameter_errors_return_bad_request(client, accept, data, message):
    client.application.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=True)
    csrf_token = _extract_csrf_token(client.get("/users/new/"))

    response = client.post(
        "/users/",
        data={"csrf_token": csrf_token, **data},
        headers={"Accept": accept},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.mimetype == "text/html"
    assert "Bad Request" in response.text
    assert message in response.text


@pytest.mark.parametrize(
    "exception, data",
    [(MissingParameter, {}), (InvalidParameter, {"user": "wrong"})],
)
def test_parameter_error_handlers_can_be_overridden(client, exception, data):
    @client.application.errorhandler(exception)
    def parameter_error(error):
        return render(json={"error": type(error).__name__}, status=400)

    csrf_token = _extract_csrf_token(client.get("/users/new/"))
    response = client.post("/users/", data={"csrf_token": csrf_token, **data})

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.get_json() == {"error": exception.__name__}


@pytest.mark.parametrize("exception", [ProgrammerError, UserError, RuntimeError])
def test_unrelated_errors_are_not_bad_requests(app, client, exception):
    app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=True)

    @app.get("/unrelated-error/")
    def unrelated_error():
        raise exception("Unexpected failure")

    with pytest.raises(exception, match="Unexpected failure"):
        client.get("/unrelated-error/")


def test_users_update(client):
    res = client.get("/users/new/")
    csrf_token = _extract_csrf_token(res)
    res = client.post(
        "/users/", data={"csrf_token": csrf_token, "user.username": "test"}
    )
    location = res.location
    res = client.get(f"{location}edit")
    csrf_token = _extract_csrf_token(res)
    res = client.put(
        location, data={"csrf_token": csrf_token, "user.username": "updated"}
    )
    assert res.status_code == HTTPStatus.FOUND


def _extract_csrf_token(res):
    match = re.search(r'name="csrf_token" value="([^"]+)"', res.text)
    if not match:
        return ""
    return match.group(1)
