from dataclasses import dataclass
from functools import cached_property
from html.parser import HTMLParser

import nh3
from markupsafe import Markup

_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "del",
    "div",
    "em",
    "h1",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "strong",
    "ul",
}
_BLOCKS = {"blockquote", "div", "h1", "li", "ol", "p", "pre", "ul"}
_CLEAN_CONTENT = {
    "script",
    "style",
    "iframe",
    "object",
    "embed",
    "svg",
    "math",
    "figure",
    "action-text-attachment",
    "trix-attachment",
}


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "br" or tag == "hr":
            self.parts.append("\n")
        elif tag in _BLOCKS and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _BLOCKS and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


@dataclass(frozen=True)
class Content:
    """An immutable rich-text body. Every HTML rendering is server-sanitized."""

    _source: str = ""

    @cached_property
    def _html(self):
        return nh3.clean(
            self._source,
            tags=_TAGS,
            attributes={"a": {"href", "title"}},
            clean_content_tags=_CLEAN_CONTENT,
            url_schemes={"http", "https", "mailto", "tel"},
            link_rel="noopener noreferrer",
        )

    def to_trix_html(self):
        return self._html

    def to_plain_text(self):
        parser = _PlainText()
        parser.feed(self._html)
        return "".join(parser.parts).strip("\n")

    def blank(self):
        return not self.to_plain_text().strip()

    def present(self):
        return not self.blank()

    def __bool__(self):
        return self.present()

    def __str__(self):
        return f'<div class="trix-content">{self._html}</div>'

    def __html__(self):
        return Markup(str(self))
