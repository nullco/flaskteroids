import pytest
from flask import Flask
from markupsafe import Markup

from flaskteroids.form import Form
from flaskteroids.helpers import button_to, form_with, link_to
from tests.assertions import HTML


@pytest.fixture
def request_context():
    app = Flask(__name__)
    app.secret_key = "html-test"
    with app.test_request_context():
        yield


def test_link_text_and_attributes_are_escaped():
    html = HTML(
        link_to("<b>Link</b> & more", '/search?q="test"&page=1', title='" onclick="bad')
    )

    assert html.text == "<b>Link</b> & more"
    assert html.has("a", href='/search?q="test"&page=1', title='" onclick="bad')
    assert not html.has("b")


def test_link_accepts_trusted_text_but_escapes_trusted_attributes():
    html = HTML(
        link_to(Markup("<strong>Link</strong>"), "/", title=Markup('" onclick="bad'))
    )

    assert html.has("strong")
    assert html.has("a", title='" onclick="bad')


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "#section",
        "../posts",
        "//example.com/posts",
        "https://example.com",
        "HTTP://example.com",
        "mailto:user@example.com",
        "tel:+1234",
    ],
)
def test_link_allows_supported_urls(path):
    assert HTML(link_to("Link", path)).has("a", href=path)


@pytest.mark.parametrize(
    "path",
    [
        "javascript:alert(1)",
        " JAVASCRIPT:alert(1)",
        "java\nscript:alert(1)",
        "java\tscript:alert(1)",
        "data:text/html,test",
        "vbscript:bad",
        "file:///tmp/file",
    ],
)
def test_link_rejects_unsafe_urls(path):
    with pytest.raises(ValueError):
        link_to("Link", path)


@pytest.mark.usefixtures("request_context")
def test_button_escapes_text_and_action():
    action = '/delete/1?next="bad"&ok=1'
    html = HTML(button_to("<b>Delete</b>", action, method="DELETE"))

    assert "<b>Delete</b>" in html.text
    assert not html.has("b")
    assert html.has("form", action=action)


@pytest.mark.usefixtures("request_context")
def test_button_accepts_trusted_text():
    html = HTML(button_to(Markup("<strong>Save</strong>"), "/records", method="POST"))

    assert html.has("strong")
    assert "Save" in html.text


@pytest.mark.usefixtures("request_context")
def test_form_escapes_action_and_method():
    action = '/posts?next="bad"&ok=1'
    method = 'PUT" onclick="bad'
    html = HTML(form_with(url=action, method=method))

    assert html.has("form", action=action)
    assert html.has("input", name="_method", value=method)


@pytest.mark.parametrize(
    "url",
    ["javascript:bad", "data:text/html,test", "mailto:user@example.com", "tel:+1234"],
)
@pytest.mark.usefixtures("request_context")
def test_form_rejects_non_http_urls(url):
    with pytest.raises(ValueError):
        form_with(url=url)


def test_collection_select_escapes_values_labels_and_prompt():
    html = HTML(
        Form("user").collection_select(
            "choice",
            [{"id": '" onclick="bad', "name": "<script>bad</script>"}],
            "id",
            "name",
            prompt="<b>Choose</b>",
        )
    )

    assert html.has("option", value='" onclick="bad')
    assert "<script>bad</script>" in html.text
    assert "<b>Choose</b>" in html.text
    assert not html.has("script")


def test_collection_select_accepts_trusted_labels_but_escapes_values():
    html = HTML(
        Form(None).collection_select(
            "choice",
            [
                {
                    "id": Markup('" onclick="bad'),
                    "name": Markup("<strong>Choice</strong>"),
                }
            ],
            "id",
            "name",
            prompt=Markup("<em>Choose</em>"),
        )
    )

    assert html.has("strong")
    assert html.has("em")
    assert html.has("option", value='" onclick="bad')


@pytest.mark.parametrize("value", ["a&b", "<choice>", '"quoted"', 1])
def test_collection_select_compares_unescaped_values(value):
    html = HTML(
        Form(None, {"choice": value}).collection_select(
            "choice",
            [{"id": value, "name": "Selected"}],
            "id",
            "name",
        )
    )

    option = next(
        attrs
        for tag, attrs in html.elements
        if tag == "option" and attrs.get("value") == str(value)
    )
    assert "selected" in option


@pytest.mark.parametrize(
    "helper",
    [
        "text_field",
        "hidden_field",
        "password_field",
        "file_field",
        "text_area",
        "label",
        "collection_select",
    ],
)
def test_field_names_and_prefixes_are_escaped(helper):
    prefix = 'user" onclick="bad'
    form = Form(prefix)
    field = '<script>bad</script>"'
    if helper == "collection_select":
        html = HTML(form.collection_select(field, [], "id", "name"))
    else:
        html = HTML(getattr(form, helper)(field))

    assert not html.has("script")
    assert all("onclick" not in attrs for _, attrs in html.elements)
    assert any(
        prefix in value
        for _, attrs in html.elements
        for value in attrs.values()
        if isinstance(value, str)
    )


def test_submit_escapes_value():
    payload = '" onclick="bad'

    assert HTML(Form(None).submit(payload)).has("input", value=payload)


def test_text_area_escapes_trusted_field_values():
    payload = "</textarea><script>bad</script>"
    html = HTML(Form(None, {"bio": Markup(payload)}).text_area("bio"))

    assert html.text == payload
    assert not html.has("script")


@pytest.mark.usefixtures("request_context")
def test_button_rejects_unsafe_action():
    with pytest.raises(ValueError):
        button_to("Delete", "javascript:bad", method="DELETE")


@pytest.mark.parametrize("value", ["<b>A</b> & B", Markup('" onclick="bad')])
def test_input_values_are_escaped_once(value):
    html = HTML(Form(None, {"name": value}).text_field("name"))

    assert html.has("input", value=str(value))


@pytest.mark.parametrize("name", ['bad" onclick="bad', "bad name", "bad=value"])
def test_link_rejects_invalid_attribute_names(name):
    with pytest.raises(ValueError):
        link_to("Link", "/", **{name: "value"})


@pytest.mark.parametrize("name", ['bad" onclick="bad', "bad name", "bad=value"])
def test_form_field_rejects_invalid_attribute_names(name):
    with pytest.raises(ValueError):
        Form(None).text_field("name", **{name: "value"})
