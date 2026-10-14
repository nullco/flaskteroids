from types import SimpleNamespace

import pytest
from flask import Flask
from markupsafe import Markup

from flaskteroids.form import Form
from flaskteroids.helpers import button_to, form_with, link_to


@pytest.fixture
def request_context():
    app = Flask(__name__)
    app.secret_key = "html-test"
    with app.test_request_context():
        yield


def test_link_text_and_attributes_are_escaped():
    html = str(
        link_to("<b>Link</b> & more", '/search?q="test"&page=1', title='" onclick="bad')
    )

    assert "&lt;b&gt;Link&lt;/b&gt; &amp; more" in html
    assert 'href="/search?q=&#34;test&#34;&amp;page=1"' in html
    assert 'title="&#34; onclick=&#34;bad"' in html
    assert "<b>Link</b>" not in html


def test_link_accepts_trusted_text_but_escapes_trusted_attributes():
    html = str(
        link_to(Markup("<strong>Link</strong>"), "/", title=Markup('" onclick="bad'))
    )

    assert "<strong>Link</strong>" in html
    assert 'title="&#34; onclick=&#34;bad"' in html


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
    assert "href=" in str(link_to("Link", path))


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
def test_button_escapes_text_and_action(mocker):
    mocker.patch(
        "flaskteroids.helpers.url_for", return_value='/delete/1?next="bad"&ok=1'
    )

    html = str(button_to("<b>Delete</b>", SimpleNamespace(id=1), "DELETE"))

    assert "&lt;b&gt;Delete&lt;/b&gt;" in html
    assert 'action="/delete/1?next=&#34;bad&#34;&amp;ok=1"' in html


@pytest.mark.usefixtures("request_context")
def test_button_accepts_trusted_text():
    assert "<strong>Save</strong>" in str(
        button_to(Markup("<strong>Save</strong>"), SimpleNamespace(id=1), "POST")
    )


@pytest.mark.usefixtures("request_context")
def test_form_escapes_action_and_method():
    html = str(form_with(url='/posts?next="bad"&ok=1', method='PUT" onclick="bad'))

    assert 'action="/posts?next=&#34;bad&#34;&amp;ok=1"' in html
    assert 'value="PUT&#34; onclick=&#34;bad"' in html


@pytest.mark.parametrize(
    "url",
    ["javascript:bad", "data:text/html,test", "mailto:user@example.com", "tel:+1234"],
)
@pytest.mark.usefixtures("request_context")
def test_form_rejects_non_http_urls(url):
    with pytest.raises(ValueError):
        form_with(url=url)


def test_collection_select_escapes_values_labels_and_prompt():
    form = Form("user")
    html = str(
        form.collection_select(
            "choice",
            [{"id": '" onclick="bad', "name": "<script>bad</script>"}],
            "id",
            "name",
            prompt="<b>Choose</b>",
        )
    )

    assert 'value="&#34; onclick=&#34;bad"' in html
    assert "&lt;script&gt;bad&lt;/script&gt;" in html
    assert "&lt;b&gt;Choose&lt;/b&gt;" in html


def test_collection_select_accepts_trusted_labels_but_escapes_values():
    html = str(
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

    assert "<strong>Choice</strong>" in html
    assert "<em>Choose</em>" in html
    assert 'value="&#34; onclick=&#34;bad"' in html


@pytest.mark.parametrize("value", ["a&b", "<choice>", '"quoted"', 1])
def test_collection_select_compares_unescaped_values(value):
    html = str(
        Form(None, {"choice": value}).collection_select(
            "choice",
            [{"id": value, "name": "Selected"}],
            "id",
            "name",
        )
    )

    assert " selected>" in html


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
    form = Form('user" onclick="bad')
    field = '<script>bad</script>"'
    if helper == "collection_select":
        html = str(form.collection_select(field, [], "id", "name"))
    else:
        html = str(getattr(form, helper)(field))

    assert "<script>" not in html.lower()
    assert 'user" onclick="bad' not in html
    assert "&#34;" in html


def test_submit_escapes_value():
    assert 'value="&#34; onclick=&#34;bad"' in str(Form(None).submit('" onclick="bad'))


def test_text_area_escapes_trusted_field_values():
    html = str(
        Form(None, {"bio": Markup("</textarea><script>bad</script>")}).text_area("bio")
    )

    assert "&lt;/textarea&gt;&lt;script&gt;bad&lt;/script&gt;" in html
    assert "<script>" not in html


@pytest.mark.usefixtures("request_context")
def test_button_rejects_unsafe_generated_action(mocker):
    mocker.patch("flaskteroids.helpers.url_for", return_value="javascript:bad")

    with pytest.raises(ValueError):
        button_to("Delete", SimpleNamespace(id=1), "DELETE")


@pytest.mark.parametrize("value", ["<b>A</b> & B", Markup('" onclick="bad')])
def test_input_values_are_escaped_once(value):
    html = str(Form(None, {"name": value}).text_field("name"))

    assert str(value) not in html
    assert "&amp;lt;" not in html
    assert "&amp;#34;" not in html


@pytest.mark.parametrize("name", ['bad" onclick="bad', "bad name", "bad=value"])
def test_link_rejects_invalid_attribute_names(name):
    with pytest.raises(ValueError):
        link_to("Link", "/", **{name: "value"})


@pytest.mark.parametrize("name", ['bad" onclick="bad', "bad name", "bad=value"])
def test_form_field_rejects_invalid_attribute_names(name):
    with pytest.raises(ValueError):
        Form(None).text_field("name", **{name: "value"})
