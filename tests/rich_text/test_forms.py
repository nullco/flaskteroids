from html.parser import HTMLParser

import pytest
from markupsafe import Markup

from flaskteroids.form import Form
from flaskteroids.rich_text import Content


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = {}
        self.feed(str(html))

    def handle_starttag(self, tag, attrs):
        self.elements[tag] = dict(attrs)


@pytest.mark.parametrize(
    "value",
    [
        "<div>Hello <strong>world</strong></div>",
        Content("<div>Hello <strong>world</strong></div>"),
        Markup("<div>Hello <strong>world</strong></div>"),
    ],
)
def test_rich_text_area_links_named_hidden_input_to_labeled_editor(value):
    form = Form("post", {"content": value})
    elements = Elements(form.rich_text_area("content"))
    hidden, editor = elements.elements["input"], elements.elements["trix-editor"]
    assert hidden["type"] == "hidden"
    assert hidden["name"] == "post[content]"
    assert hidden["id"] == editor["input"]
    assert editor["id"] == Elements(form.label("content")).elements["label"]["for"]
    assert hidden["value"] == "<div>Hello <strong>world</strong></div>"


def test_rich_text_area_escapes_attributes_and_sanitizes_initial_content():
    form = Form(
        "post", {"content": '<img src=x onerror="alert(1)"><strong>Safe</strong>'}
    )
    elements = Elements(
        form.rich_text_area("content", placeholder='A "quoted" placeholder')
    )
    assert elements.elements["input"]["value"] == "<strong>Safe</strong>"
    assert elements.elements["trix-editor"]["placeholder"] == 'A "quoted" placeholder'
    assert set(elements.elements) == {"input", "trix-editor"}


def test_rich_text_area_supports_custom_editor_id_and_explicit_value():
    elements = Elements(
        Form(None).rich_text_area("content", id="custom", value="<em>Body</em>")
    )
    assert elements.elements["trix-editor"]["id"] == "custom"
    assert elements.elements["trix-editor"]["input"] == elements.elements["input"]["id"]
    assert elements.elements["input"]["name"] == "content"
    assert elements.elements["input"]["value"] == "<em>Body</em>"
