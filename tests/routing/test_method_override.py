from io import BytesIO

import pytest
from flask import request

from flaskteroids.helpers import csrf_token
from tests.routing.method_override_cases import METHOD_OVERRIDE_CASES


@pytest.mark.parametrize("case", METHOD_OVERRIDE_CASES, ids=lambda case: case["name"])
def test_requests_normalize_method_overrides(routing_app, case):
    headers = {}
    if "header" in case:
        headers["X-HTTP-Method-Override"] = case["header"]
    response = routing_app.test_client().open(
        "/probe?" + case.get("query", ""),
        method=case.get("method", "POST"),
        data=case.get("body", ""),
        content_type=case.get("content_type", "application/x-www-form-urlencoded"),
        headers=headers,
    )
    assert routing_app.config["METHODS"] == [case["effective"]]
    if case["name"] in {
        "malformed_percent_uses_header",
        "conflicting_shape_uses_header",
        "interleaved_shape_uses_header",
    }:
        assert response.status_code == 400
    elif case["effective"] in {"LINK", "UNLINK", "OPTIONS"}:
        assert response.status_code == 404
    else:
        assert response.status_code == 200
        if case["effective"] != "HEAD":
            expected_action = {
                "GET": "show",
                "POST": "create",
                "PUT": "update",
                "PATCH": "update",
                "DELETE": "destroy",
            }[case["effective"]]
            assert response.json["action"] == expected_action


@pytest.mark.parametrize("first", ["post", "delete"])
def test_override_dispatch_is_independent_of_registration_order(
    make_routing_app, first
):
    def register(route):
        methods = [first, "delete" if first == "post" else "post"]
        for method in methods:
            getattr(route, method)(
                "/operation", to=f"probes#{'create' if method == 'post' else 'destroy'}"
            )

    client = make_routing_app(register).test_client()
    assert client.post("/operation").json["action"] == "create"
    response = client.post("/operation", data={"_method": "delete"})
    assert response.json == {
        "action": "destroy",
        "method": "DELETE",
        "params": {"_method": "delete"},
    }


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_actual_and_form_verbs_reach_the_same_resource_action(routing_app, method):
    client = routing_app.test_client()
    actual = client.open("/products/1", method=method, data={"title": "kept"})
    submitted = client.post(
        "/products/1", data={"title": "kept", "_method": method.lower()}
    )
    assert actual.status_code == submitted.status_code == 200
    assert actual.json["action"] == submitted.json["action"]
    assert submitted.json["method"] == method
    assert submitted.json["params"] == {
        "id": 1,
        "title": "kept",
        "_method": method.lower(),
    }


def test_route_bindings_take_precedence_over_query_and_form(routing_app):
    response = routing_app.test_client().post(
        "/products/1?id=999&query=kept", data={"id": "888", "_method": "patch"}
    )
    assert response.json["params"] == {"id": 1, "query": "kept", "_method": "patch"}


@pytest.mark.parametrize("transport", ["verb", "form"])
def test_unroutable_resource_method_returns_not_found(make_routing_app, transport):
    app = make_routing_app(lambda route: route.resource("probe", only=["create"]))
    response = app.test_client().open(
        "/probe",
        method="PATCH" if transport == "verb" else "POST",
        data={"_method": "PATCH"} if transport == "form" else None,
    )
    assert response.status_code == 404


def test_native_endpoints_retain_method_contracts_and_override_parameters(routing_app):
    @routing_app.post("/native")
    def native():
        return {"method": request.method, "override": request.form.get("_method")}

    client = routing_app.test_client()
    assert client.post("/native", data={"_method": "delete"}).json == {
        "method": "POST",
        "override": "delete",
    }
    assert client.delete("/native").status_code == 405


def test_native_post_at_a_shared_path_keeps_its_original_dispatch(make_routing_app):
    app = make_routing_app(lambda route: route.delete("/shared", to="probes#destroy"))

    @app.post("/shared")
    def native():
        return "native"

    assert (
        app.test_client().post("/shared", data={"_method": "delete"}).text == "native"
    )
    assert app.test_client().delete("/shared").json["action"] == "destroy"


def test_overridden_multipart_retains_uploads_fields_and_token(routing_app):
    routing_app.config.action_controller.allow_forgery_protection = True

    @routing_app.get("/token")
    def issue_token():
        return csrf_token()

    client = routing_app.test_client()
    token = client.get("/token").text
    response = client.post(
        "/products/1",
        data={
            "_method": "patch",
            "csrf_token": token,
            "product[title]": "kept",
            "product[image]": (BytesIO(b"image bytes"), "photo.txt"),
        },
    )
    assert response.status_code == 200
    assert response.json["params"] == {
        "id": 1,
        "_method": "patch",
        "product": {
            "title": "kept",
            "image": {"filename": "photo.txt", "content": "image bytes"},
        },
    }


@pytest.mark.parametrize("limit", ["MAX_CONTENT_LENGTH", "MAX_FORM_MEMORY_SIZE"])
def test_override_parsing_enforces_request_limits(routing_app, limit):
    routing_app.config[limit] = 32
    response = routing_app.test_client().post(
        "/probe",
        data={"_method": "delete", "title": "x" * 100},
        content_type="multipart/form-data",
    )
    assert response.status_code == 413


def test_custom_form_parser_is_preserved_during_normalization(routing_app):
    from flask import Request
    from werkzeug.formparser import FormDataParser

    class CustomParser(FormDataParser):
        def parse(self, *args, **kwargs):
            stream, form, files = super().parse(*args, **kwargs)
            form = form.copy()
            form.add("parser", "application")
            return stream, form, files

    class CustomRequest(Request):
        form_data_parser_class = CustomParser

    routing_app.request_class = CustomRequest
    response = routing_app.test_client().post("/probe", data={"_method": "delete"})
    assert response.json["params"]["parser"] == "application"
    assert response.json["action"] == "destroy"


def test_multipart_part_limits_reject_override_dispatch(routing_app):
    routing_app.config["MAX_FORM_PARTS"] = 1
    response = routing_app.test_client().post(
        "/probe",
        data={"_method": "delete", "title": "kept"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 413


def test_get_query_override_keeps_the_safe_action(routing_app):
    response = routing_app.test_client().get("/probe?_method=DELETE")
    assert response.json["action"] == "show"
    assert response.json["method"] == "GET"


def test_file_valued_override_blocks_header_fallback(routing_app):
    response = routing_app.test_client().post(
        "/probe",
        data={"_method": (BytesIO(b"DELETE"), "method.txt")},
        headers={"X-HTTP-Method-Override": "DELETE"},
    )
    assert response.status_code == 200
    assert response.json["action"] == "create"
    assert response.json["params"]["_method"]["filename"] == "method.txt"


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_transport_mapping_keys_remain_bounded_string_keys(routing_app, method):
    values = {"_method[1000000000]": "DELETE"}
    response = routing_app.test_client().open(
        "/probe",
        method=method,
        query_string=values if method == "GET" else None,
        data=values if method == "POST" else None,
        headers={"X-HTTP-Method-Override": "DELETE"},
    )
    assert response.status_code == 200
    assert response.json["method"] == method
    assert response.json["params"]["_method"] == {"1000000000": "DELETE"}


def test_conflicting_query_transport_shapes_reject_dispatch(routing_app):
    response = routing_app.test_client().get(
        "/probe?_method[]=PUT&_method[1000000000]=DELETE"
    )
    assert response.status_code == 400


def test_managed_route_miss_is_not_replaced_by_a_csrf_error(make_routing_app):
    app = make_routing_app(lambda route: route.resource("probe", only=["create"]))
    app.config.action_controller.allow_forgery_protection = True
    assert (
        app.test_client().post("/probe", data={"_method": "delete"}).status_code == 404
    )


@pytest.mark.parametrize(
    "limit", ["MAX_CONTENT_LENGTH", "MAX_FORM_MEMORY_SIZE", "MAX_FORM_PARTS"]
)
def test_early_parse_limits_keep_their_status_with_csrf_enabled(routing_app, limit):
    routing_app.config.action_controller.allow_forgery_protection = True
    routing_app.config[limit] = 1
    response = routing_app.test_client().post(
        "/probe",
        data={"_method": "delete", "title": "kept"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 413


def test_malformed_multipart_rejects_header_dispatch(routing_app):
    response = routing_app.test_client().post(
        "/probe",
        data=b"--boundary\r\ninvalid",
        content_type="multipart/form-data; boundary=boundary",
        headers={"X-HTTP-Method-Override": "DELETE"},
    )
    assert response.status_code == 400
