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
        "<p>Hello <strong>world</strong></p>",
        Content("<p>Hello <strong>world</strong></p>"),
        Markup("<p>Hello <strong>world</strong></p>"),
    ],
)
def test_rich_text_area_renders_a_named_and_labeled_form_control(value):
    form = Form("post", {"content": value})
    elements = Elements(form.rich_text_area("content"))
    editor = elements.elements["lexxy-editor"]
    assert editor["name"] == "post[content]"
    assert editor["id"] == Elements(form.label("content")).elements["label"]["for"]
    assert editor["value"] == "<p>Hello <strong>world</strong></p>"
    assert editor["attachments"] == "false"


def test_rich_text_area_escapes_attributes_and_sanitizes_initial_content():
    form = Form(
        "post", {"content": '<img src=x onerror="alert(1)"><strong>Safe</strong>'}
    )
    elements = Elements(
        form.rich_text_area("content", placeholder='A "quoted" placeholder')
    )
    editor = elements.elements["lexxy-editor"]
    assert editor["value"] == "<strong>Safe</strong>"
    assert editor["placeholder"] == 'A "quoted" placeholder'
    assert set(elements.elements) == {"lexxy-editor"}


def test_rich_text_area_supports_custom_editor_id_and_explicit_value():
    elements = Elements(
        Form(None).rich_text_area("content", id="custom", value="<em>Body</em>")
    )
    editor = elements.elements["lexxy-editor"]
    assert editor["id"] == "custom"
    assert editor["name"] == "content"
    assert editor["value"] == "<em>Body</em>"
