import pytest
from jinja2 import Environment
from markupsafe import Markup

from flaskteroids.rich_text import Content


def test_content_renders_formatted_html_with_trix_wrapper():
    content = Content("<h1>Welcome</h1><div>Hello <strong>world</strong></div>")
    rendered = (
        Environment(autoescape=True)
        .from_string("{{ content }}")
        .render(content=content)
    )
    assert '<div class="trix-content">' in rendered
    assert "<strong>world</strong>" in rendered
    assert content.to_plain_text() == "Welcome\nHello world"


@pytest.mark.parametrize(
    "source",
    [
        '<div onclick="alert(1)">Hello<script>alert(1)</script></div>',
        '<div>Hello<img src=x onerror="alert(1)"></div>',
        "<svg><script>alert(1)</script></svg><div>Hello</div>",
        "<style>body{display:none}</style><div>Hello</div>",
        '<iframe srcdoc="<script>alert(1)</script>"></iframe><div>Hello</div>',
        '<figure data-trix-attachment="{}">Secret file</figure><div>Hello</div>',
        '<action-text-attachment sgid="stolen">Secret file</action-text-attachment><div>Hello</div>',
    ],
)
def test_content_strips_active_html_and_embeds(source):
    content = Content(source)
    assert content.to_trix_html() == "<div>Hello</div>"
    assert content.to_plain_text() == "Hello"


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "java\nscript:alert(1)", "data:text/html,evil"]
)
def test_content_rejects_executable_links(url):
    assert "href=" not in Content(f'<a href="{url}">Link</a>').to_trix_html()


def test_content_keeps_safe_links_and_discards_editor_metadata():
    html = Content(
        '<a href="https://example.com" data-trix-attachment="{}">Link</a>'
    ).to_trix_html()
    assert 'href="https://example.com"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "data-trix" not in html


@pytest.mark.parametrize(
    "source", ["", "<div><br></div>", "<div>&nbsp; </div>", "<script>evil</script>"]
)
def test_content_reports_visually_empty_text_as_blank(source):
    assert Content(source).blank()
    assert not Content(source)


def test_deeply_nested_editor_metadata_is_removed():
    metadata = "[" * 2000 + "]" * 2000
    body = Content(
        f'<figure data-trix-attachment="{metadata}"></figure><div>Safe</div>'
    )
    assert body.to_trix_html() == "<div>Safe</div>"


def test_invalid_unicode_and_signature_characters_are_safe():
    body = Content(
        "<div>Safe"
        + chr(0xD800)
        + '</div><action-text-attachment sgid="?.token"></action-text-attachment>'
    )
    assert body.to_plain_text() == "Safe?"


def test_plain_text_is_an_ordinary_string_that_templates_escape():
    value = Content("&lt;script&gt;alert(1)&lt;/script&gt;").to_plain_text()
    assert value == "<script>alert(1)</script>"
    assert not isinstance(value, Markup)
    rendered = (
        Environment(autoescape=True).from_string("{{ value }}").render(value=value)
    )
    assert rendered.startswith("&lt;script&gt;")
