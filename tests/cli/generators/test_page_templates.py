import pytest
from flask import render_template
from jinja2 import DictLoader

from flaskteroids.cli.generators.authentication.generator import (
    generate as authentication,
)
from flaskteroids.cli.generators.controller.generator import generate as controller
from flaskteroids.cli.generators.scaffold.generator import generate as scaffold
from tests.assertions import HTML
from tests.routing.conftest import make_routing_app as make_routing_app
from tests.routing.conftest import records as records
from tests.routing.conftest import routing_app as routing_app


@pytest.fixture
def generated_views(mocker):
    artifacts = {}
    builder = mocker.Mock()
    builder.file.side_effect = artifacts.__setitem__
    for generator in ("controller", "scaffold", "authentication"):
        mocker.patch(
            f"flaskteroids.cli.generators.{generator}.generator.ArtifactsBuilder",
            return_value=builder,
        )
    mocker.patch("flaskteroids.cli.generators.scaffold.generator.model.generate")
    mocker.patch("flaskteroids.cli.generators.authentication.generator.migrations")

    controller("Pages", ["home"], skip_routes=True)
    scaffold("Product", ["name:string"])
    authentication()
    return {
        path.removeprefix("app/views/"): source
        for path, source in artifacts.items()
        if path.startswith("app/views/")
    }


@pytest.mark.parametrize(
    "page,heading",
    [
        ("pages/home.html", "Pages#home"),
        ("sessions/new.html", None),
        ("passwords/new.html", "Forgot your password?"),
        ("passwords/edit.html", "Update your password"),
        ("products/index.html", "Products"),
        ("products/new.html", "New product"),
        ("products/edit.html", "Edit product"),
        ("products/show.html", None),
    ],
)
@pytest.mark.parametrize("layout", ["full.html", "frame.html"])
def test_generated_pages_render_the_selected_layout_and_body(
    routing_app, records, generated_views, page, heading, layout
):
    routing_app.jinja_loader = DictLoader(
        generated_views
        | {
            name: f'<main data-layout="{name}">{{% block body %}}{{% endblock %}}</main>'
            for name in ("full.html", "frame.html")
        }
    )
    html = HTML(
        render_template(
            page,
            layout=layout,
            product=records.product,
            products=[records.product],
            params={},
            flash={},
            url_for=lambda endpoint, **options: f"/{endpoint}",
        )
    )
    assert html.has("main", **{"data-layout": layout})
    if heading is not None:
        assert html.has("h1")
        assert heading in html.text
    if page in {"products/index.html", "products/show.html"}:
        assert html.has("div", id=f"product_{records.product.id}")
        assert "Product" in html.text
    elif page != "pages/home.html":
        assert html.has("form")
    assert not html.has("turbo-frame")
    assert not html.has("turbo-stream")


def test_generated_record_partial_uses_new_record_dom_identity(
    routing_app, records, generated_views
):
    routing_app.jinja_loader = DictLoader(generated_views)
    html = HTML(render_template("products/_product.html", product=records.new_product))
    assert html.has("div", id="new_product")
    assert "Entered" in html.text
