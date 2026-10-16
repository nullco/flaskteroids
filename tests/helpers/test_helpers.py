import pytest

from flaskteroids.helpers import button_to, csrf_token, form_with, link_to, render
from tests.assertions import HTML


@pytest.fixture
def url_for(mocker):
    return mocker.patch("flaskteroids.helpers.url_for")


@pytest.fixture
def model_instance(mocker):
    model_instance = mocker.Mock()
    model_instance.__class__.__name__ = "TestModel"
    model_instance.id = 1
    model_instance.configure_mock(**{"_form_data.return_value": {"name": "test"}})
    return model_instance


@pytest.fixture
def render_template(mocker):
    render_template = mocker.patch("flaskteroids.helpers.render_template")
    render_template.return_value = "<div>test</div>"
    return render_template


@pytest.fixture
def request_ctx(app):
    with app.test_request_context():
        yield


@pytest.mark.usefixtures("request_ctx")
class TestHelpers:
    def test_link_to_generates_anchor_tag(self):
        result = link_to("Click me", "/test", class_="btn", id="link")
        html = HTML(result)
        assert html.has("a", href="/test", class_="btn", id="link")
        assert html.text == "Click me"

    def test_button_to_generates_delete_form(self, model_instance, url_for):
        url_for.return_value = "/delete/1"
        result = button_to("Delete", model_instance, "delete")
        html = HTML(result)
        assert html.has("form", method="DELETE", action="/delete/1")
        assert html.has("button", type="submit")
        assert "Delete" in html.text

    @pytest.mark.parametrize(
        "identity, action, override", [(None, "/create", ""), (1, "/update/1", "PUT")]
    )
    def test_form_with_selects_model_route_and_method_override(
        self, model_instance, url_for, identity, action, override
    ):
        model_instance.id = identity
        url_for.return_value = action

        result = form_with(model=model_instance, caller=lambda _: "<input>")

        html = HTML(result)
        assert html.has("form", action=action, method="POST")
        assert html.has("input", name="_method", value=override)
        if identity is None:
            url_for.assert_called_with("create_test_model")
        else:
            url_for.assert_called_with("update_test_model", id=identity)

    def test_render_calls_render_template(self, render_template):
        result = render("test.html", name="value")
        render_template.assert_called_once_with("test.html", name="value")
        assert "<div>test</div>" in str(result)

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
