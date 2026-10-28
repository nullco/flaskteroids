import pytest
from jinja2 import Environment
from markupsafe import Markup

from flaskteroids.rich_text import Content
from tests.assertions import HTML


def test_content_renders_formatted_html_with_lexxy_wrapper():
    content = Content("<h1>Welcome</h1><div>Hello <strong>world</strong></div>")
    rendered = (
        Environment(autoescape=True)
        .from_string("{{ content }}")
        .render(content=content)
    )
    assert '<div class="lexxy-content">' in rendered
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
        '<action-text-attachment sgid="stolen">Secret file</action-text-attachment><div>Hello</div>',
    ],
)
def test_content_strips_active_html_and_embeds(source):
    content = Content(source)
    assert content.to_editor_html() == "<div>Hello</div>"
    assert content.to_plain_text() == "Hello"


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "java\nscript:alert(1)", "data:text/html,evil"]
)
def test_content_rejects_executable_links(url):
    assert "href=" not in Content(f'<a href="{url}">Link</a>').to_editor_html()


def test_content_keeps_safe_links_and_discards_editor_metadata():
    html = Content(
        '<a href="https://example.com" data-editor-state="{}">Link</a>'
    ).to_editor_html()
    assert 'href="https://example.com"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "data-editor-state" not in html


@pytest.mark.parametrize(
    "source", ["", "<div><br></div>", "<div>&nbsp; </div>", "<script>evil</script>"]
)
def test_content_reports_visually_empty_text_as_blank(source):
    assert Content(source).blank()
    assert not Content(source)


def test_invalid_unicode_and_signature_characters_are_safe():
    body = Content(
        "<div>Safe"
        + chr(0xD800)
        + '</div><action-text-attachment sgid="?.token"></action-text-attachment>'
    )
    assert body.to_plain_text() == "Safe?"


@pytest.mark.parametrize(
    "source",
    [
        "<h2>Heading</h2><h3>Subheading</h3><h4>Section</h4>",
        "<p><u>Underline</u> <s>Strike</s> <code>Inline</code></p>",
        '<pre data-language="python">print("hello")</pre>',
        '<figure class="lexxy-content__table-wrapper"><table><tbody><tr>'
        '<th colspan="2">Heading</th><td>Cell</td></tr></tbody></table></figure>',
        '<ol start="3"><li value="4">Item</li></ol>',
    ],
)
def test_content_preserves_editor_formatting(source):
    assert Content(source).to_html() == source


@pytest.mark.parametrize(
    "color",
    ["red", "#abcdef", "rgb(20, 30, 40)", "oklch(80% 0.2 60)", "var(--highlight-bg-1)"],
)
def test_content_preserves_highlight_colors(color):
    html = Content(f'<mark style="background-color: {color}">Text</mark>').to_html()
    assert HTML(html).has("mark", style=f"background-color: {color}")


@pytest.mark.parametrize(
    "style",
    [
        "position: fixed; inset: 0",
        "background-image: url(https://tracker.example/pixel)",
        "color: expression(alert(1))",
        "color: url(https://tracker.example/pixel)",
        r"color: u\\72l(https://tracker.example/pixel)",
        "color: u/**/rl(https://tracker.example/pixel)",
        "color: var(--x, url(https://tracker.example/pixel))",
        "color: red !important",
        "--highlight-bg-1: url(https://tracker.example/pixel)",
        r'color: var(--x, \\"; background-image:url(https://tracker.example/pixel))',
    ],
)
def test_content_rejects_active_or_layout_affecting_styles(style):
    html = Content(f"<mark style='{style}'>Text</mark>").to_html()
    assert HTML(html).has("mark")
    assert "style=" not in html


def test_plain_text_separates_table_cells_and_rows():
    body = Content(
        "<table><tbody><tr><th>A</th><th>B</th></tr>"
        "<tr><td>One</td><td>Two</td></tr></tbody></table>"
    )
    assert body.to_plain_text() == "A\tB\nOne\tTwo"


def test_plain_text_is_an_ordinary_string_that_templates_escape():
    value = Content("&lt;script&gt;alert(1)&lt;/script&gt;").to_plain_text()
    assert value == "<script>alert(1)</script>"
    assert not isinstance(value, Markup)
    rendered = (
        Environment(autoescape=True).from_string("{{ value }}").render(value=value)
    )
    assert rendered.startswith("&lt;script&gt;")
