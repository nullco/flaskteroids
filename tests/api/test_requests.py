import json

import pytest
from flask import Response
from werkzeug.datastructures import WWWAuthenticate
from werkzeug.exceptions import MethodNotAllowed, Unauthorized

from flaskteroids.routes import RouteHelper


@pytest.mark.parametrize("body", [{"title": "Hello", "items": [1, False, None]}, {}])
def test_json_body_reaches_controller_parameters(api_client, body):
    response = api_client.post("/probes", json=body)

    assert response.status_code == 200
    assert response.get_json()["params"] == body


@pytest.mark.parametrize("body", [[1, {"title": "Hello"}], "text", 42, False, None])
def test_non_object_json_is_available_under_json_key(api_client, body):
    response = api_client.post(
        "/probes", data=json.dumps(body), content_type="application/json"
    )

    assert response.status_code == 200
    assert response.get_json()["params"] == {"_json": body}


def test_path_and_query_parameters_take_precedence(api_client):
    response = api_client.patch(
        "/probes/7?name=query&id=8",
        json={"id": 9, "name": "body", "nested": {"valid": False}},
    )

    assert response.get_json() == {
        "id": 7,
        "name": "query",
        "nested": {"valid": False},
    }


@pytest.mark.parametrize(
    "content_type", ["application/json", "application/vnd.example+json"]
)
def test_malformed_json_returns_json_bad_request(api_client, content_type):
    response = api_client.post("/probes", data="{", content_type=content_type)

    assert response.status_code == 400
    assert response.get_json()["status"] == 400


def test_empty_json_request_has_empty_parameters(api_client):
    response = api_client.post("/probes", data=b"", content_type="application/json")

    assert response.status_code == 200
    assert response.get_json()["params"] == {}


def test_json_wrapping_keeps_original_values(api_client):
    response = api_client.post("/wrappeds", json={"title": "Hello"})

    assert response.get_json() == {"title": "Hello", "wrapped": {"title": "Hello"}}


def test_json_wrapping_preserves_explicit_root(api_client):
    response = api_client.post(
        "/wrappeds", json={"wrapped": {"title": "Nested"}, "title": "Outer"}
    )

    assert response.get_json()["wrapped"] == {"title": "Nested"}


def test_json_wrapping_supports_custom_root(api_client):
    response = api_client.post("/custom_wrappeds", json={"title": "Hello"})

    assert response.get_json()["payload"] == {"title": "Hello"}


def test_forms_keep_their_parameter_structure(api_client):
    response = api_client.post(
        "/probes", data={"post[title]": "Hello", "ids[]": ["1", "2"]}
    )

    assert response.get_json()["params"] == {
        "post": {"title": "Hello"},
        "ids": ["1", "2"],
    }


def test_api_requests_use_native_http_methods(api_client):
    response = api_client.post(
        "/probes",
        json={"_method": "DELETE"},
        headers={"X-HTTP-Method-Override": "DELETE"},
    )

    assert response.status_code == 200
    assert response.get_json()["method"] == "POST"


@pytest.mark.parametrize("api_only", [False, True])
def test_api_cache_validators_are_independent_of_browser_headers(
    api_application_factory, api_only
):
    client = api_application_factory(api_only=api_only).test_client()
    first = client.get("/conditional")
    repeated = client.get(
        "/conditional",
        headers={"Turbo-Frame": "editor", "If-None-Match": first.headers["ETag"]},
    )

    assert first.status_code == 200
    assert repeated.status_code == 304
    assert "Turbo-Frame" not in first.vary


def test_api_controller_accepts_file_responses(api_client):
    response = api_client.get("/download")

    assert response.status_code == 200
    assert response.mimetype == "application/octet-stream"
    assert response.data == b"file contents"


def test_api_action_without_response_returns_no_content(api_client):
    response = api_client.get("/empty")

    assert response.status_code == 204
    assert response.data == b""


@pytest.mark.parametrize(
    "path", ["/", "/unknown", "/probes/new", "/probes/1/edit", "/probes.turbo_stream"]
)
def test_missing_api_routes_return_json_not_found(api_client, path):
    response = api_client.get(path)

    assert response.status_code == 404
    assert response.get_json()["status"] == 404


def test_api_errors_preserve_retry_after_header(api_client):
    response = api_client.get("/limited")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"
    assert response.get_json()["status"] == 429


def test_http_errors_preserve_protocol_headers(api_app):
    @api_app.get("/native-method-error")
    def method_error():
        raise MethodNotAllowed(valid_methods=["PATCH"])

    @api_app.get("/native-auth-error")
    def auth_error():
        raise Unauthorized(
            www_authenticate=WWWAuthenticate("basic", {"realm": "example"})
        )

    client = api_app.test_client()
    assert client.get("/native-method-error").headers["Allow"] == "PATCH"
    assert "Basic" in client.get("/native-auth-error").headers["WWW-Authenticate"]


def test_unexpected_errors_hide_private_details(api_client):
    response = api_client.get("/failure")

    assert response.status_code == 500
    assert response.is_json
    assert "private implementation detail" not in response.text


def test_debugging_preserves_exception_propagation(api_app):
    api_app.config["PROPAGATE_EXCEPTIONS"] = True

    with pytest.raises(RuntimeError, match="private implementation detail"):
        api_app.test_client().get("/failure")


def test_api_defaults_leave_cookie_sessions_unavailable(api_client):
    response = api_client.post("/cookie")

    assert response.status_code == 500
    assert "Set-Cookie" not in response.headers


def test_api_resources_use_five_action_defaults(api_app):
    rules = {rule.rule for rule in api_app.url_map.iter_rules()}

    assert "/probes.json" in rules
    assert "/account" in rules
    assert "/account/new" not in rules
    assert "/account/edit" not in rules
    assert "/parents/<int:parent_id>/children" in rules
    assert "/parents/<int:parent_id>/children/new" not in rules


def test_api_route_helpers_reject_unavailable_turbo_format(api_app):
    with api_app.test_request_context():
        with pytest.raises(ValueError, match="Unsupported format"):
            RouteHelper("probe_path")(1, format="turbo_stream")


def test_api_and_browser_applications_keep_independent_defaults(
    api_application_factory,
):
    browser = api_application_factory(api_only=False)
    api = api_application_factory()
    browser_client = browser.test_client()
    api_client = api.test_client()

    assert browser_client.post("/browser").status_code == 400
    assert api_client.post("/probes", json={}).status_code == 200
    assert browser_client.post("/probes", json={}).status_code == 200
    assert browser_client.get("/").status_code == 200
    assert api_client.get("/").status_code == 404
    assert "flaskteroids.turbo" in browser.extensions
    assert "flaskteroids.turbo" not in api.extensions

    token = browser_client.get("/browser").get_json()["csrf_token"]
    response = browser_client.post("/browser", headers={"X-CSRF-TOKEN": token})
    assert response.status_code == 200
    assert not browser_client.get("/unknown").is_json


def test_api_authentication_generation_rejects_before_writing(api_app):
    result = api_app.test_cli_runner().invoke(args=["generate", "authentication"])

    assert result.exit_code == 1
    assert "not yet supported" in result.output
    assert not (api_app.project_root / "app/models/user.py").exists()


def test_browser_controller_stays_protected_in_api_application(api_client):
    response = api_client.post("/browser", json={})

    assert response.status_code == 400


def test_native_responses_are_not_rewritten_as_json(api_app):
    @api_app.get("/native")
    def native():
        return Response("custom response", status=202, mimetype="text/plain")

    response = api_app.test_client().get("/native")

    assert response.status_code == 202
    assert response.text == "custom response"
    assert response.mimetype == "text/plain"
