import pytest
from flask import render_template_string
from markupsafe import Markup

from flaskteroids.helpers import button_to, form_with, link_to
from tests.assertions import HTML
from tests.routing.conftest import make_routing_app as make_routing_app
from tests.routing.conftest import records as records
from tests.routing.conftest import routing_app as routing_app


def test_model_form_call_accepts_turbo_options_without_changing_transport(records):
    html = HTML(
        render_template_string(
            "{% call(form) form_with(model=product, id='editor-form', "
            "data={'turbo_frame': 'editor', 'turbo': false}) %}"
            "{{ form.text_field('name') }}{{ form.file_field('image') }}"
            "{% endcall %}",
            product=records.product,
        )
    )

    assert html.has(
        "form",
        id="editor-form",
        action=f"/products/{records.product.id}",
        method="POST",
        enctype="multipart/form-data",
        **{"data-turbo-frame": "editor", "data-turbo": "false"},
    )
    assert html.has("input", name="product[name]", value="Product")
    assert html.has("input", name="_method", value="PATCH")
    assert html.has("input", name="csrf_token")


@pytest.fixture
def request_context(routing_app):
    with routing_app.test_request_context():
        yield


@pytest.mark.usefixtures("request_context")
@pytest.mark.parametrize("helper", [link_to, button_to, form_with])
def test_tag_helpers_share_nested_options_and_boolean_rules(helper):
    options = {
        "class_": "panel",
        "hidden": True,
        "disabled": False,
        "title": None,
        "data": {
            "turbo_frame": "editor",
            "turbo_method": "delete",
            "turbo": False,
            "ids": [1, 2],
            "options": {"mode": "inline"},
            "missing": None,
        },
        "aria": {"busy": True, "labelled_by": "heading"},
    }
    if helper is form_with:
        result = helper(url="/posts", **options)
        tag = "form"
    else:
        result = helper("Submit", "/posts", **options)
        tag = "a" if helper is link_to else "button"
    html = HTML(result)
    assert html.has(
        tag,
        **{
            "class": "panel",
            "hidden": "hidden",
            "data-turbo-frame": "editor",
            "data-turbo-method": "delete",
            "data-turbo": "false",
            "data-ids": "[1,2]",
            "data-options": '{"mode":"inline"}',
            "aria-busy": "true",
            "aria-labelled-by": "heading",
        },
    )
    attrs = next(attrs for name, attrs in html.elements if name == tag)
    assert {"disabled", "title", "data-missing", "class_"}.isdisjoint(attrs)


@pytest.mark.usefixtures("request_context")
def test_button_form_options_remain_separate_from_button_options():
    html = HTML(
        button_to(
            "Delete",
            "/posts/1",
            method="DELETE",
            form={"class_": "delete-form", "data": {"turbo_frame": "editor"}},
            class_="delete-button",
            data={"turbo_confirm": "Really delete?"},
        )
    )
    assert html.has(
        "form",
        method="POST",
        action="/posts/1",
        **{"class": "delete-form", "data-turbo-frame": "editor"},
    )
    assert html.has(
        "button",
        type="submit",
        **{"class": "delete-button", "data-turbo-confirm": "Really delete?"},
    )
    assert html.has("input", name="_method", value="DELETE")
    assert html.has("input", name="csrf_token")


@pytest.mark.usefixtures("request_context")
@pytest.mark.parametrize(
    "value", ['"><img src=x onerror="bad">', Markup('" onclick="bad')]
)
def test_form_attributes_escape_plain_and_trusted_values(value):
    result = form_with(url="/posts", title=value, data={"value": value})
    html = HTML(result)
    assert html.has("form", title=str(value), **{"data-value": str(value)})
    assert not html.has("img")
    assert all("onclick" not in attrs for _, attrs in html.elements)


@pytest.mark.usefixtures("request_context")
@pytest.mark.parametrize(
    "options",
    [
        {'bad" onclick': "bad"},
        {"bad name": "bad"},
        {"data": {'bad" name': "bad"}},
        {"aria": {"bad=name": "bad"}},
    ],
)
def test_form_rejects_invalid_attribute_names(options):
    with pytest.raises(ValueError, match="attribute name"):
        form_with(url="/posts", **options)


@pytest.mark.usefixtures("request_context")
def test_get_form_options_preserve_omitted_action_and_csrf_rules():
    html = HTML(
        form_with(url=False, method="GET", multipart=True, data={"turbo": False})
    )
    assert html.has("form", method="GET", enctype="multipart/form-data")
    assert "action" not in html.forms[0]["attributes"]
    assert not html.has("input", name="csrf_token")
    assert not html.has("input", name="_method")
