"""HTML-only Turbo helpers; response handling belongs to the controller layer."""

from flask import has_request_context, request
from markupsafe import Markup, escape

from flaskteroids._html import tag_attributes, validate_url
from flaskteroids.routes import _polymorphic_path
from flaskteroids.turbo.identifiers import dom_id
from flaskteroids.turbo.rendering import render

_MISSING = object()


def _compound_id(values):
    return "_".join(
        _compound_id(value) if isinstance(value, (list, tuple)) else str(value)
        for value in values
    )


def turbo_frame_tag(*ids, src=None, target=None, caller=None, **attrs):
    """Build a frame, accepting a record and prefix or compound string IDs.

    Jinja ``{% call turbo_frame_tag(record) %}...{% endcall %}`` captures trusted
    rendered HTML. Attributes (including Markup values) are always escaped.
    """
    if not ids:
        raise ValueError("turbo_frame_tag requires an identifier")
    first = ids[0]
    if isinstance(first, type) or callable(getattr(first, "to_key", None)):
        if len(ids) > 2:
            raise ValueError("Record frame IDs accept one optional prefix")
        identifier = dom_id(first, ids[1] if len(ids) == 2 else None)
    else:
        identifier = _compound_id(ids)
    if src is not None:
        if callable(getattr(src, "to_param", None)) or isinstance(src, (list, tuple)):
            src = _polymorphic_path(src)
        src = validate_url(src)
    options = tag_attributes({**attrs, "id": identifier, "src": src, "target": target})
    body = caller() if caller is not None else ""
    return Markup(f"<turbo-frame {options}>{body}</turbo-frame>")


def _target(value):
    if isinstance(value, type) or callable(getattr(value, "to_key", None)):
        return dom_id(value)
    return value


class TurboStreamBuilder:
    """Build individual stream tags, safe to concatenate with Markup.join.

    The public singleton is stateless. View contexts bind a renderer so stream
    partials share the same helper instance and owner as the enclosing view.
    """

    def __init__(self, *, renderer=render):
        self._render = renderer

    def _content(self, target, content, *, partial, locals, caller):
        if caller is not None:
            return Markup(caller())
        if partial is not None:
            return self._render(partial=partial, locals=locals)
        if content is _MISSING or content is None:
            if callable(getattr(target, "to_partial_path", None)):
                return self._render(target, locals=locals)
            return Markup("")
        if callable(getattr(content, "to_partial_path", None)):
            return self._render(content, locals=locals)
        return escape(content)

    def _action(
        self,
        name,
        target,
        content,
        *,
        selector=False,
        partial=None,
        locals=None,
        caller=None,
        method=None,
        **attrs,
    ):
        options = dict(attrs)
        options["action"] = name
        if target is not None:
            options["targets" if selector else "target"] = (
                target if selector else _target(target)
            )
        if method is not None:
            options["method"] = method
        body = ""
        if name not in {"remove", "refresh"}:
            html = self._content(
                None if selector else target,
                content,
                partial=partial,
                locals=locals,
                caller=caller,
            )
            body = f"<template>{html}</template>"
        return Markup(f"<turbo-stream {tag_attributes(options)}>{body}</turbo-stream>")

    def action(self, name, target=None, content=_MISSING, **options):
        """Build a custom action addressed to an element or record DOM ID."""
        return self._action(name, target, content, **options)

    def action_all(self, name, targets, content=_MISSING, **options):
        """Build a custom action addressed to a CSS selector (kept verbatim)."""
        return self._action(name, targets, content, selector=True, **options)

    def append(self, target, content=_MISSING, **options):
        return self.action("append", target, content, **options)

    def prepend(self, target, content=_MISSING, **options):
        return self.action("prepend", target, content, **options)

    def before(self, target, content=_MISSING, **options):
        return self.action("before", target, content, **options)

    def after(self, target, content=_MISSING, **options):
        return self.action("after", target, content, **options)

    def replace(self, target, content=_MISSING, **options):
        return self.action("replace", target, content, **options)

    def update(self, target, content=_MISSING, **options):
        return self.action("update", target, content, **options)

    def remove(self, target, **options):
        return self.action("remove", target, **options)

    def refresh(self, *, request_id=_MISSING, **options):
        """Refresh the page, forwarding the originating Turbo request ID."""
        if request_id is _MISSING:
            request_id = (
                request.headers.get("X-Turbo-Request-Id")
                if has_request_context()
                else None
            )
        return self.action("refresh", **{**options, "request-id": request_id})

    def append_all(self, targets, content=_MISSING, **options):
        return self.action_all("append", targets, content, **options)

    def prepend_all(self, targets, content=_MISSING, **options):
        return self.action_all("prepend", targets, content, **options)

    def before_all(self, targets, content=_MISSING, **options):
        return self.action_all("before", targets, content, **options)

    def after_all(self, targets, content=_MISSING, **options):
        return self.action_all("after", targets, content, **options)

    def replace_all(self, targets, content=_MISSING, **options):
        return self.action_all("replace", targets, content, **options)

    def update_all(self, targets, content=_MISSING, **options):
        return self.action_all("update", targets, content, **options)

    def remove_all(self, targets, **options):
        return self.action_all("remove", targets, **options)


turbo_stream = TurboStreamBuilder()
