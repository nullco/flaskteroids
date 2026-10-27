import pytest
from flask import render_template_string

import flaskteroids.routes as helpers
from flaskteroids.routes import (
    edit_product_path,
    edit_product_subscriber_path,
    new_product_path,
    new_product_subscriber_path,
    product_path,
    product_subscriber_path,
    product_subscribers_path,
    product_url,
    products_path,
    session_path,
)


@pytest.mark.parametrize(
    "helper,bindings,path",
    [
        (products_path, (), "/products"),
        (product_path, (1,), "/products/1"),
        (new_product_path, (), "/products/new"),
        (edit_product_path, (1,), "/products/1/edit"),
        (product_subscribers_path, (1,), "/products/1/subscribers"),
        (product_subscriber_path, (1, 2), "/products/1/subscribers/2"),
        (new_product_subscriber_path, (1,), "/products/1/subscribers/new"),
        (edit_product_subscriber_path, (1, 2), "/products/1/subscribers/2/edit"),
    ],
)
def test_stream_resource_helpers_generate_suffix_routes_and_preserve_queries(
    routing_app, helper, bindings, path
):
    with routing_app.test_request_context():
        assert helper(*bindings, format="turbo_stream", page=2) == (
            path + ".turbo_stream?page=2"
        )
        assert (
            render_template_string(
                "{{ helper(*bindings, format='turbo_stream') }}",
                helper=helper,
                bindings=bindings,
            )
            == path + ".turbo_stream"
        )
    response = routing_app.test_client().get(path + ".turbo_stream?q=kept")
    assert response.status_code == 200
    assert response.json["params"]["q"] == "kept"


def test_stream_resource_url_uses_external_url_and_record_binding(routing_app, records):
    with routing_app.test_request_context():
        assert product_url(records.product, format="turbo_stream") == (
            f"http://localhost/products/{records.product.id}.turbo_stream"
        )


@pytest.mark.parametrize("suffix", [".turbo_stream", ".turbo_stream/"])
@pytest.mark.parametrize("method,action", [("patch", "update"), ("delete", "destroy")])
def test_stream_suffix_routes_preserve_method_override_and_form_params(
    routing_app, suffix, method, action
):
    response = routing_app.test_client().post(
        f"/products/1/subscribers/2{suffix}",
        data={"_method": method, "subscriber[email]": "entered@example.com"},
    )
    assert response.status_code == 200
    assert response.json["action"] == action
    assert response.json["method"] == method.upper()
    assert response.json["params"] == {
        "product_id": 1,
        "id": 2,
        "_method": method,
        "subscriber": {"email": "entered@example.com"},
    }


@pytest.mark.parametrize("name", ["fish", "equipment"])
@pytest.mark.parametrize("nested", [False, True])
def test_uncountable_stream_routes_keep_collection_and_member_helpers(
    make_routing_app, name, nested
):
    def register(route):
        if nested:
            route.resources("products", nested=lambda child: child.resources(name))
        else:
            route.resources(name)

    app = make_routing_app(register)
    prefix = "product_" if nested else ""
    bindings = (1,) if nested else ()
    collection = f"/products/1/{name}" if nested else f"/{name}"
    with app.test_request_context():
        assert (
            getattr(helpers, f"{prefix}{name}_index_path")(
                *bindings, format="turbo_stream"
            )
            == collection + ".turbo_stream"
        )
        assert (
            getattr(helpers, f"{prefix}{name}_path")(
                *bindings, 2, format="turbo_stream"
            )
            == collection + "/2.turbo_stream"
        )
    client = app.test_client()
    assert client.get(collection + ".turbo_stream").json["action"] == "index"
    assert client.get(collection + "/2.turbo_stream").json["action"] == "show"


def test_singular_stream_routes_dispatch_without_a_member_binding(make_routing_app):
    app = make_routing_app(
        lambda route: route.resource("product", only=["show", "update"])
    )
    with app.test_request_context():
        assert product_path(format="turbo_stream") == "/product.turbo_stream"
    client = app.test_client()
    assert client.get("/product.turbo_stream").json["action"] == "show"
    response = client.post(
        "/product.turbo_stream", data={"_method": "patch", "title": "kept"}
    )
    assert response.json["action"] == "update"
    assert response.json["params"] == {"_method": "patch", "title": "kept"}


def test_singular_stream_routes_respect_selected_actions(make_routing_app):
    app = make_routing_app(
        lambda route: route.resource("session", only=["create", "destroy"])
    )
    with app.test_request_context():
        assert session_path(format="turbo_stream") == "/session.turbo_stream"
    assert app.test_client().get("/session.turbo_stream").status_code == 404


def test_custom_named_routes_keep_existing_format_semantics(make_routing_app):
    app = make_routing_app(
        lambda route: route.get("/item/<id>", to="products#show", aka="product")
    )
    with app.test_request_context():
        with pytest.raises(ValueError, match="Unsupported format"):
            product_path(1, format="turbo_stream")
