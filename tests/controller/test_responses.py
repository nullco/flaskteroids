from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from http import HTTPStatus
from uuid import UUID

import pytest

from flaskteroids.exceptions import DoubleRenderError
from flaskteroids.model import Errors


@pytest.mark.parametrize(
    ("value", "status"),
    [
        ({}, 200),
        ([], 200),
        ("", 200),
        (0, 200),
        (False, 200),
        (None, 200),
        ({"name": "Alice"}, 200),
        ([1, "two", None], 200),
        ("hello", 200),
        (1.5, 200),
        (True, 200),
        (None, HTTPStatus.CREATED),
        ({}, HTTPStatus.UNPROCESSABLE_ENTITY),
    ],
)
def test_json_render_preserves_values_and_status(
    response_client, render_template, value, status
):
    client = response_client(
        lambda controller: controller.render(json=value, status=status)
    )

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

    response = response_client(
        lambda controller: controller.render(json=Record(), status=201)
    ).get("/response/")

    assert response.status_code == 201
    assert response.get_json() == value

    response = response_client(
        lambda controller: controller.render(
            json={"items": [Record()], "tuple": (Record(),)}, status=201
        )
    ).get("/response/")

    assert response.status_code == 201
    assert response.mimetype == "application/json"
    assert response.get_json() == {"items": [value], "tuple": [value]}


def test_json_protocol_serializes_nested_results(response_client):
    class Record:
        def __json__(self):
            return {"id": 1}

    class Envelope:
        def __json__(self):
            return {"records": [Record()], "empty": None}

    response = response_client(
        lambda controller: controller.render(json={"data": Envelope()})
    ).get("/response/")

    assert response.get_json() == {"data": {"records": [{"id": 1}], "empty": None}}


@pytest.mark.parametrize("base", [dict, list])
def test_json_protocol_takes_precedence_over_container_contents(response_client, base):
    class Collection(base):
        def __json__(self):
            return {"custom": True}

    response = response_client(
        lambda controller: controller.render(json=[Collection()])
    ).get("/response/")

    assert response.get_json() == [{"custom": True}]


def test_json_preserves_flask_provider_types(response_client):
    @dataclass
    class Metadata:
        count: int

    payload = {
        "values": [date(2026, 1, 2), Decimal("1.25"), UUID(int=1), Metadata(count=2)]
    }
    client = response_client(lambda controller: controller.render(json=payload))
    expected = client.application.json.loads(client.application.json.dumps(payload))

    assert client.get("/response/").get_json() == expected


def test_json_preserves_custom_provider_default(response_client, mocker):
    class CustomValue:
        pass

    client = response_client(
        lambda controller: controller.render(json={"items": [CustomValue()]})
    )
    original_default = client.application.json.default

    def default(value):
        if isinstance(value, CustomValue):
            return "custom value"
        return original_default(value)

    mocker.patch.object(client.application.json, "default", side_effect=default)

    assert client.get("/response/").get_json() == {"items": ["custom value"]}


def test_json_rejects_unsupported_objects(response_client):
    client = response_client(
        lambda controller: controller.render(json={"items": [object()]})
    )

    with pytest.raises(TypeError, match="not JSON serializable"):
        client.get("/response/")


@pytest.mark.parametrize(
    "messages", [[], ["Name is blank"], ["Name is blank", "Email is invalid"]]
)
def test_json_errors_are_message_lists(response_client, messages):
    errors = Errors()
    for message in messages:
        errors.append(("validation", message))

    response = response_client(
        lambda controller: controller.render(json=errors, status=422)
    ).get("/response/")

    assert response.status_code == 422
    assert response.mimetype == "application/json"
    assert response.get_json() == messages


def test_html_render_preserves_status(response_client, render_template):
    render_template.return_value = "<p>Invalid form</p>"
    response = response_client(
        lambda controller: controller.render("new", status=422)
    ).get("/response/")

    assert response.status_code == 422
    assert response.mimetype == "text/html"
    assert response.text == "<p>Invalid form</p>"


def test_implicit_html_render_selects_action_template(response_client, render_template):
    render_template.return_value = "<p>Default template</p>"
    response = response_client(lambda controller: None).get("/response/")

    assert response.status_code == 200
    assert response.text == "<p>Default template</p>"


@pytest.mark.parametrize("returned", [None, "ignored", {}])
def test_render_records_response_without_ending_the_action(response_client, returned):
    observed = []

    def action(controller):
        controller.render(json={"rendered": True}, status=202)
        observed.append(controller.response.status_code)
        return returned

    response = response_client(action).get("/response/")
    assert response.status_code == 202
    assert response.get_json() == {"rendered": True}
    assert observed == [202]


def test_render_without_arguments_selects_the_active_action(
    response_client, render_template
):
    render_template.return_value = "Current action"
    response = response_client(lambda controller: controller.render(status=422)).get(
        "/response/"
    )
    assert response.status_code == 422
    assert response.text == "Current action"
    assert render_template.call_args.args == ("responses/show.html",)


@pytest.mark.parametrize("second", ["template", "json"])
def test_render_rejects_a_second_response(response_client, second):
    def action(controller):
        controller.render(json={"first": True})
        if second == "template":
            controller.render("new")
        else:
            controller.render(json=None)

    with pytest.raises(DoubleRenderError):
        response_client(action).get("/response/")


def test_failed_template_render_allows_a_recovery_response(
    response_client, render_template
):
    render_template.side_effect = ValueError("Rendering failed")

    def action(controller):
        with pytest.raises(ValueError):
            controller.render("new")
        controller.render(json={"recovered": True}, status=422)

    response = response_client(action).get("/response/")
    assert response.status_code == 422
    assert response.get_json() == {"recovered": True}


def test_explicit_empty_html_response_preserves_empty_body(
    response_client, render_template
):
    response = response_client(lambda controller: "").get("/response/")

    assert response.status_code == 200
    assert response.data == b""
    render_template.assert_not_called()
