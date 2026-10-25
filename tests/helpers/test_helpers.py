import pytest
from jinja2 import DictLoader
from markupsafe import Markup

from flaskteroids.helpers import button_to, csrf_token, form_with, link_to, render
from tests.assertions import HTML


@pytest.fixture
def request_ctx(app):
    with app.test_request_context():
        yield


@pytest.mark.usefixtures("request_ctx")
class TestHelpers:
    def test_link_to_generates_anchor_tag(self):
        result = link_to("Click me", "/test", class_="btn", id="link")
        html = HTML(result)
        assert html.has("a", href="/test", id="link", **{"class": "btn"})
        assert html.text == "Click me"

    def test_button_to_generates_delete_form(self):
        result = button_to("Delete", "/records/1", method="delete")
        html = HTML(result)
        assert html.has("form", method="POST", action="/records/1")
        assert html.has("input", name="_method", value="DELETE")
        assert html.has("button", type="submit")
        assert "Delete" in html.text

    def test_render_returns_safe_html_with_escaped_template_values(self, app):
        app.jinja_loader = DictLoader({"test.html": "<div>{{ name }}</div>"})
        result = render("test.html", name="<value>")
        assert isinstance(result, Markup)
        assert HTML(result).text == "<value>"
        assert "&lt;value&gt;" in result

    def test_form_with_detects_file_fields(self):
        result = form_with(url="/upload", caller=lambda form: form.file_field("avatar"))
        html = HTML(result)
        assert html.has("form", enctype="multipart/form-data")
        assert html.has("input", type="file")
        assert html.has("input", name="csrf_token")

    def test_form_with_uses_default_encoding_for_text_fields(self):
        result = form_with(url="/upload", caller=lambda form: form.text_field("name"))
        html = HTML(result)
        form = next(attrs for tag, attrs in html.elements if tag == "form")
        assert form.get("enctype", "application/x-www-form-urlencoded") == (
            "application/x-www-form-urlencoded"
        )

    def test_form_with_supports_explicit_multipart(self):
        result = form_with(url="/upload", multipart=True)
        assert HTML(result).has("form", enctype="multipart/form-data")

    def test_csrf_token_generates_token(self):
        result = csrf_token()
        assert result
