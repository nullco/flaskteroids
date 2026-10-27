import pytest
from flask import render_template_string

from flaskteroids.helpers import button_to, form_with
from flaskteroids.routes import category_path, product_path, product_subscriber_path
from tests.assertions import HTML


@pytest.fixture(params=["url", "new", "persisted", "nested_new", "nested_persisted"])
def destination(request, records):
    choices = {
        "url": ("/custom", "/custom", "POST"),
        "new": (records.new_product, "/products", "POST"),
        "persisted": (records.product, f"/products/{records.product.id}", "PATCH"),
        "nested_new": (
            [records.product, records.new_subscriber],
            f"/products/{records.product.id}/subscribers",
            "POST",
        ),
        "nested_persisted": (
            (records.product, records.subscriber),
            f"/products/{records.product.id}/subscribers/{records.subscriber.id}",
            "PATCH",
        ),
    }
    return choices[request.param]


def assert_form_transport(html, action, method):
    assert html.has("form", action=action, method="GET" if method == "GET" else "POST")
    assert html.has("input", name="csrf_token") == (method != "GET")
    assert html.has("input", name="_method") == (method not in {"GET", "POST"})
    if method not in {"GET", "POST"}:
        assert html.has("input", name="_method", value=method)


@pytest.mark.parametrize("method", [None, "GET", "POST", "PUT", "PATCH", "DELETE"])
def test_buttons_infer_destinations_and_respect_explicit_methods(destination, method):
    model, url, inferred = destination
    html = HTML(button_to("Submit", model, method=method))
    assert_form_transport(html, url, inferred if method is None else method)


@pytest.mark.parametrize("method", [None, "DELETE"])
def test_buttons_submit_to_the_effective_resource_action(
    routing_app, destination, method
):
    target, _, inferred = destination
    if isinstance(target, str):
        target = "/probe"
    routing_app.config.controller.allow_forgery_protection = True

    @routing_app.get("/button")
    def button():
        return button_to("Submit", target, method=method)

    client = routing_app.test_client()
    markup = HTML(client.get("/button").text)
    form = markup.forms[0]
    response = client.open(
        form["attributes"]["action"],
        method=form["attributes"]["method"],
        data=form["fields"],
    )
    if method == "DELETE" and inferred == "POST" and not isinstance(target, str):
        assert response.status_code == 404
    else:
        assert response.status_code == 200
        assert response.json["action"] == (
            "destroy"
            if method == "DELETE"
            else "create"
            if inferred == "POST"
            else "update"
        )


@pytest.mark.parametrize("method", [None, "POST", "PUT", "GET"])
def test_forms_keep_inference_independent_of_explicit_url(destination, method):
    model, inferred_url, inferred = destination
    if isinstance(model, str):
        html = HTML(form_with(url=model, method=method))
        assert_form_transport(html, model, "POST" if method is None else method)
        return
    for explicit_url in [None, "/custom"]:
        html = HTML(form_with(model=model, url=explicit_url, method=method))
        assert_form_transport(
            html,
            inferred_url if explicit_url is None else explicit_url,
            inferred if method is None else method,
        )


@pytest.mark.parametrize("url", [None, False, "", "/custom"])
def test_model_form_distinguishes_inferred_omitted_and_empty_actions(records, url):
    html = HTML(form_with(model=records.product, url=url))
    form = next(attrs for tag, attrs in html.elements if tag == "form")
    if url is False:
        assert "action" not in form
    else:
        assert form["action"] == (
            f"/products/{records.product.id}" if url is None else url
        )
    assert html.has("input", name="_method", value="PATCH")


@pytest.mark.parametrize("scope", [None, "signup", ""])
def test_nested_forms_use_child_values_and_explicit_scope(records, scope):
    html = HTML(
        form_with(
            model=[records.product, records.subscriber],
            scope=scope,
            caller=lambda form: form.email_field("email"),
        )
    )
    prefix = "subscriber" if scope is None else scope
    assert html.has(
        "input",
        name=f"{prefix}[email]" if prefix else "email",
        value="entered@example.com",
    )


def test_failed_nested_submission_retains_child_values_errors_and_destination(records):
    child = records.new_subscriber
    child.email = ""
    assert child.save() is False
    html = HTML(
        render_template_string(
            "{% call(form) form_with(model=[product, subscriber]) %}"
            '{{ form.email_field("email") }}{% endcall %}',
            product=records.product,
            subscriber=child,
        )
    )
    assert child.errors
    assert html.has("form", action=f"/products/{records.product.id}/subscribers")
    assert html.has("input", name="subscriber[email]", value="")


@pytest.mark.parametrize("explicit_url", [None, "/custom"])
def test_model_form_retains_invalid_numeric_input_and_multipart(records, explicit_url):
    product = records.product
    assert product.update(quantity="12garbage") is False
    html = HTML(
        form_with(
            model=product,
            url=explicit_url,
            caller=lambda form: (
                str(form.number_field("quantity")) + str(form.file_field("image"))
            ),
        )
    )
    assert product.errors
    assert html.has("input", name="product[quantity]", value="12garbage")
    assert html.has("form", enctype="multipart/form-data")


@pytest.mark.parametrize("explicit_url", [None, "/custom"])
def test_nested_form_excludes_secrets_even_with_explicit_url(records, explicit_url):
    records.subscriber.password_digest = "secret digest"
    html = HTML(
        form_with(
            model=[records.product, records.subscriber],
            url=explicit_url,
            caller=lambda form: form.text_field("password_digest"),
        )
    )
    assert html.has("input", name="subscriber[password_digest]", value="")


def test_buttons_keep_form_and_button_attributes_separate(records):
    html = HTML(
        button_to(
            'Save " & <b>bold</b>',
            records.product,
            form={"id": "save-form", "data-owner": '"unsafe'},
            id="save-button",
            title='"unsafe',
        )
    )
    assert html.has("form", id="save-form", **{"data-owner": '"unsafe'})
    assert html.has("button", id="save-button", title='"unsafe', type="submit")
    assert not html.has("b")


def test_assigned_id_on_a_new_model_still_infers_create(records):
    records.new_product.id = 123
    html = HTML(form_with(model=records.new_product))
    assert_form_transport(html, "/products", "POST")


@pytest.mark.parametrize("destination_kind", ["inferred", "explicit", "nested"])
def test_file_fields_and_secret_exclusion_survive_destination_choices(
    records, destination_kind
):
    child = records.new_subscriber
    child.password_digest = "secret digest"
    if destination_kind == "inferred":
        # The child is also routable as a top-level resource for this case.
        from flask import current_app

        current_app.extensions["flaskteroids.routes"].resources("subscribers")
    model = [records.product, child] if destination_kind == "nested" else child
    html = HTML(
        form_with(
            model=model,
            url="/custom" if destination_kind == "explicit" else None,
            caller=lambda form: (
                form.file_field("image") + form.text_field("password_digest")
            ),
        )
    )
    assert html.has("form", enctype="multipart/form-data")
    assert html.has("input", name="subscriber[password_digest]", value="")
    assert html.has("input", name="csrf_token")


def test_member_helpers_require_identity_and_use_public_parameter_protocol(records):
    assert product_path(records.product) == product_path(records.product.id)
    assert product_subscriber_path(
        records.product, records.subscriber
    ) == product_subscriber_path(
        product_id=records.product.id, id=records.subscriber.id
    )
    with pytest.raises(ValueError, match="persisted"):
        product_path(records.new_product)
    assert HTML(button_to("Create", records.new_product)).has(
        "form", action="/products"
    )


def test_slug_helpers_use_to_param_instead_of_guessing_attributes(records, routing_app):
    # Add a different resource's custom binding without changing products' identity.
    routing_app.extensions["flaskteroids.routes"].resources("categories", param="slug")
    assert category_path(records.category) == "/categories/some-slug"
    assert category_path(slug="explicit") == "/categories/explicit"
    assert product_path(records.product) == f"/products/{records.product.id}"


@pytest.mark.parametrize(
    "model,error", [([], ValueError), ([1, 2], TypeError), (object(), TypeError)]
)
def test_model_forms_reject_unsupported_destinations(records, model, error):
    with pytest.raises(error):
        form_with(model=model)
