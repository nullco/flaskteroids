from dataclasses import dataclass, field
from functools import cached_property
from html.parser import HTMLParser

import nh3
from markupsafe import Markup, escape

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
    "figure",
    "figcaption",
    "action-text-attachment",
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
    "trix-attachment",
}


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "hr"}:
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
    """An immutable body with verified, storage-backed attachments."""

    _source: str = ""
    _record: object = field(default=None, repr=False, compare=False)

    @cached_property
    def _parts(self):
        from flaskteroids.rich_text.embeds import Fragment

        html = nh3.clean(
            self._source.encode("utf-8", errors="replace").decode(),
            tags=_TAGS,
            attributes={
                "a": {"href", "title"},
                "figure": {"data-trix-attachment", "data-trix-attributes"},
                "action-text-attachment": {"sgid", "caption"},
            },
            clean_content_tags=_CLEAN_CONTENT,
            url_schemes={"http", "https", "mailto", "tel"},
            link_rel="noopener noreferrer",
        )
        return Fragment(html).parts

    @cached_property
    def _blobs(self):
        from flaskteroids.rich_text.embeds import Reference, resolve

        return resolve(
            [part for part in self._parts if isinstance(part, Reference)], self._record
        )

    @property
    def attachables(self):
        return list({blob.id: blob for blob in self._blobs.values()}.values())

    def append_attachables(self, attachables):
        from flaskteroids.rich_text.embeds import Reference, canonical

        return Content(
            self.to_html()
            + "".join(
                canonical(Reference(blob.attachable_sgid)) for blob in attachables
            ),
            _record=self._record,
        )

    def to_html(self):
        from flaskteroids.rich_text.embeds import Reference, canonical

        return "".join(
            canonical(part)
            if isinstance(part, Reference) and part.sgid in self._blobs
            else ""
            if isinstance(part, Reference)
            else part
            for part in self._parts
        )

    def _render(self, *, editor=False):
        from flaskteroids.rich_text.embeds import Reference, previewable, render

        output, gallery = [], []

        def finish_gallery():
            if len(gallery) > 1 and not editor:
                output.append(
                    '<div class="attachment-gallery">' + "".join(gallery) + "</div>"
                )
            else:
                output.extend(gallery)
            gallery.clear()

        for part in self._parts:
            if isinstance(part, Reference):
                blob = self._blobs.get(part.sgid)
                if blob is not None:
                    html = render(part, blob, editor=editor)
                    if previewable(blob):
                        gallery.append(html)
                    else:
                        finish_gallery()
                        output.append(html)
            else:
                if part.strip():
                    finish_gallery()
                output.append(part)
        finish_gallery()
        return "".join(output)

    def to_trix_html(self):
        return self._render(editor=True)

    def to_plain_text(self):
        from flaskteroids.rich_text.embeds import Reference

        parts = []
        for part in self._parts:
            if isinstance(part, Reference):
                if blob := self._blobs.get(part.sgid):
                    parts.append(str(escape(part.caption or blob.filename)))
            else:
                parts.append(part)
        parser = _PlainText()
        parser.feed("".join(parts))
        return "".join(parser.parts).strip("\n")

    def blank(self):
        return not self.to_plain_text().strip()

    def present(self):
        return not self.blank()

    def __bool__(self):
        return self.present()

    def __str__(self):
        return f'<div class="trix-content">{self._render()}</div>'

    def __html__(self):
        return Markup(str(self))
