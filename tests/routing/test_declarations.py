import pytest
from flask import render_template_string


@pytest.mark.parametrize("method", ["get", "post", "put", "patch", "delete"])
def test_individual_verbs_dispatch_to_named_actions(make_routing_app, method):
    app = make_routing_app(
        lambda route: getattr(route, method)(
            "/operation", to="probes#show", as_="operation"
        )
    )
    with app.test_request_context():
        assert render_template_string("{{ operation_path() }}") == "/operation"
    response = app.test_client().open("/operation", method=method.upper())
    assert response.status_code == 200
    assert response.json["method"] == method.upper()


def test_absolute_helper_retains_a_declared_name_ending_in_path(make_routing_app):
    app = make_routing_app(
        lambda route: route.get(
            "/operation/<id>", to="probes#show", as_="operation_path"
        )
    )
    with app.test_request_context():
        assert (
            render_template_string("{{ operation_path_url(1) }}")
            == "http://localhost/operation/1"
        )


def test_root_route_generates_a_public_helper_and_dispatches(make_routing_app):
    app = make_routing_app(lambda route: route.root(to="probes#index"))
    with app.test_request_context():
        assert render_template_string("{{ root_path() }}") == "/"
    assert app.test_client().get("/").json["action"] == "index"


def test_empty_only_restricts_parent_actions_without_removing_children(
    make_routing_app,
):
    app = make_routing_app(
        lambda route: route.resources(
            "products",
            only=[],
            nested=lambda child: child.resources("subscribers", only=["create"]),
        )
    )
    client = app.test_client()
    assert client.get("/products").status_code == 404
    assert client.post("/products/1/subscribers").json["params"] == {"product_id": 1}
