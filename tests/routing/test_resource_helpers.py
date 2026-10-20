import pytest
from flask import render_template_string

from flaskteroids.exceptions import ProgrammerError
from flaskteroids.routes import (
    edit_product_path,
    edit_product_subscriber_path,
    new_product_path,
    new_product_subscriber_path,
    product_path,
    product_subscriber_path,
    product_subscribers_path,
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
def test_helpers_generate_conventional_paths_and_dispatch(
    routing_app, helper, bindings, path
):
    with routing_app.test_request_context():
        assert helper(*bindings) == path
        assert (
            render_template_string(
                "{{ helper(*bindings) }}", helper=helper, bindings=bindings
            )
            == path
        )
    assert routing_app.test_client().get(path).status_code == 200


def test_parent_and_child_keep_distinct_member_bindings(routing_app):
    client = routing_app.test_client()
    assert client.get("/products/1").json["params"] == {"id": 1}
    assert client.get("/products/1/subscribers").json["params"] == {"product_id": 1}
    assert client.get("/products/1/subscribers/2").json["params"] == {
        "product_id": 1,
        "id": 2,
    }


def test_custom_parent_binding_retains_converter_and_ancestor_meaning(make_routing_app):
    app = make_routing_app(
        lambda route: route.resources(
            "products",
            param="int:sku",
            nested=lambda child: child.resources("subscribers"),
        )
    )
    client = app.test_client()
    assert client.get("/products/12").json["params"] == {"sku": 12}
    assert client.get("/products/12/subscribers/3").json["params"] == {
        "product_sku": 12,
        "id": 3,
    }
    assert client.get("/products/word/subscribers").status_code == 404
    with app.test_request_context():
        assert (
            product_subscriber_path(product_sku=12, id=3)
            == "/products/12/subscribers/3"
        )


def test_slug_parent_binding_and_two_ancestors_keep_their_identities(make_routing_app):
    app = make_routing_app(
        lambda route: route.resources(
            "shops",
            param="slug",
            nested=lambda shop: shop.resources(
                "products", nested=lambda product: product.resources("subscribers")
            ),
        )
    )
    response = app.test_client().patch("/shops/store/products/1/subscribers/2")
    assert response.json["params"] == {"shop_slug": "store", "product_id": 1, "id": 2}
    with app.test_request_context():
        assert (
            render_template_string("{{ shop_product_subscriber_path('store', 1, 2) }}")
            == "/shops/store/products/1/subscribers/2"
        )


def test_same_child_under_different_parents_has_unambiguous_helpers(make_routing_app):
    def register(route):
        route.resources("products", nested=lambda child: child.resources("subscribers"))
        route.resources(
            "categories", nested=lambda child: child.resources("subscribers")
        )

    app = make_routing_app(register)
    with app.test_request_context():
        assert (
            render_template_string("{{ product_subscriber_path(1, 2) }}")
            == "/products/1/subscribers/2"
        )
        assert (
            render_template_string("{{ category_subscriber_path(3, 4) }}")
            == "/categories/3/subscribers/4"
        )


def test_resource_helpers_exist_for_only_create_and_destroy(make_routing_app):
    def register(route):
        route.resource("session", only=["create", "destroy"])
        route.resources("products", only=["create", "destroy"])

    app = make_routing_app(register)
    with app.test_request_context():
        assert session_path() == "/session"
        assert products_path() == "/products"
        assert product_path(1) == "/products/1"
    client = app.test_client()
    # No SessionsController is needed to prove that an excluded action never dispatches.
    assert client.get("/session").status_code == 404
    assert client.get("/products/1").status_code == 404
    assert (
        client.post("/products/1", data={"_method": "delete"}).json["action"]
        == "destroy"
    )


@pytest.mark.parametrize("suffix", ["", "/", ".json", ".json/"])
def test_canonical_and_optional_slash_write_paths_preserve_body(routing_app, suffix):
    response = routing_app.test_client().post(
        f"/products/1{suffix}", data={"_method": "patch", "title": "kept"}
    )
    assert response.status_code == 200
    assert response.json["params"] == {"id": 1, "_method": "patch", "title": "kept"}


def test_json_helper_format_and_query_values_are_explicit(routing_app):
    with routing_app.test_request_context():
        assert product_path(1, format="json", page=2) == "/products/1.json?page=2"
        with pytest.raises(ValueError, match="Unsupported format"):
            product_path(1, format="xml")


@pytest.mark.parametrize(
    "bindings,values,error",
    [
        ((1,), {}, ValueError),
        ((1, 2), {"id": 3}, TypeError),
        ((1, 2, 3), {}, TypeError),
        ((None, 2), {}, ValueError),
    ],
)
def test_nested_helpers_reject_unresolved_or_duplicate_bindings(
    routing_app, bindings, values, error
):
    with routing_app.test_request_context("/products/1/subscribers/2"):
        with pytest.raises(error):
            product_subscriber_path(*bindings, **values)


def test_helpers_use_the_active_application_in_python_and_templates(make_routing_app):
    a = make_routing_app(
        lambda route: route.get("/one/<id>", to="products#show", as_="product")
    )
    b = make_routing_app(
        lambda route: route.get("/two/<id>", to="products#show", as_="product")
    )
    for app, prefix in [(a, "one"), (b, "two"), (a, "one")]:
        app.config.update(SERVER_NAME="example.test", APPLICATION_ROOT="/store")
        with app.app_context():
            assert product_path(1) == f"/store/{prefix}/1"
            assert (
                render_template_string("{{ product_url(1) }}")
                == f"http://example.test/store/{prefix}/1"
            )


def test_named_helper_collisions_are_configuration_errors(routing_app):
    route = routing_app.extensions["flaskteroids.routes"]
    routing_app.jinja_env.globals["dashboard_path"] = lambda: "application helper"
    with pytest.raises(ProgrammerError, match="dashboard_path"):
        route.get("/dashboard", to="products#show", as_="dashboard")


def test_duplicate_resource_declarations_report_endpoint_collision(routing_app):
    with pytest.raises(ProgrammerError, match="endpoint"):
        routing_app.extensions["flaskteroids.routes"].resources("products")
