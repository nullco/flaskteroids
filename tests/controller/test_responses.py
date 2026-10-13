from http import HTTPStatus

import pytest
from flask import Flask

from flaskteroids.controller import ActionController, init, render
from flaskteroids.model import Errors


@pytest.fixture(scope="module")
def response_client():
    controllers = []

    def build(action):
        class ResponsesController(ActionController):
            def show(self):
                return action()

        init(ResponsesController)
        controllers.append(ResponsesController)
        app = Flask(__name__)
        app.testing = True
        app.add_url_rule("/response/", view_func=lambda: ResponsesController().show())
        return app.test_client()

    return build


@pytest.mark.parametrize(
    "value",
    [
        {},
        [],
        "",
        0,
        False,
        None,
        {"name": "Alice"},
        [1, "two", None],
        "hello",
        1.5,
        True,
    ],
)
@pytest.mark.parametrize(
    "status", [200, HTTPStatus.CREATED, HTTPStatus.UNPROCESSABLE_ENTITY]
)
def test_json_values_and_status(response_client, render_template, value, status):
    client = response_client(lambda: render(json=value, status=status))

    response = client.get("/response/")

    assert response.status_code == status
    assert response.mimetype == "application/json"
    assert response.get_json() == value
    assert type(response.get_json()) is type(value)
    render_template.assert_not_called()


@pytest.mark.parametrize("value", [{}, [], None, 0, False, {"id": 1}])
def test_json_protocol_preserves_empty_values_and_status(response_client, value):
    class Record:
        def __bool__(self):
            return False

        def __json__(self):
            return value

    response = response_client(lambda: render(json=Record(), status=201)).get(
        "/response/"
    )

    assert response.status_code == 201
    assert response.get_json() == value


@pytest.mark.parametrize(
    "messages", [[], ["Name is blank"], ["Name is blank", "Email is invalid"]]
)
def test_json_errors_are_message_lists(response_client, messages):
    errors = Errors()
    for message in messages:
        errors.append(("validation", message))

    response = response_client(lambda: render(json=errors, status=422)).get(
        "/response/"
    )

    assert response.status_code == 422
    assert response.mimetype == "application/json"
    assert response.get_json() == messages


def test_html_render_preserves_status(response_client, render_template):
    render_template.return_value = "<p>Invalid form</p>"
    response = response_client(lambda: render("new", status=422)).get("/response/")

    assert response.status_code == 422
    assert response.mimetype == "text/html"
    assert response.text == "<p>Invalid form</p>"


def test_implicit_html_render_still_works(response_client, render_template):
    render_template.return_value = "<p>Default template</p>"
    response = response_client(lambda: None).get("/response/")

    assert response.status_code == 200
    assert response.text == "<p>Default template</p>"


def test_explicit_empty_html_response_is_not_replaced(response_client, render_template):
    response = response_client(lambda: "").get("/response/")

    assert response.status_code == 200
    assert response.data == b""
    render_template.assert_not_called()
