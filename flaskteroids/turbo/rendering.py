"""Shared HTML rendering below helpers, controllers, and helper discovery."""

from pathlib import PurePosixPath

from flask import g, has_request_context, render_template
from markupsafe import Markup

from flaskteroids._view_helpers import active_view, render_assigns, render_scope


def _partial_template(path):
    path = PurePosixPath(path)
    name = path.name
    if not name.startswith("_"):
        name = "_" + name
    if not path.suffix:
        name += ".html"
    return str(path.with_name(name))


def render(template=None, *, partial=None, locals=None, **kwargs):
    """Render an exact template, a conventional partial, or a record partial.

    Partial names such as ``posts/post`` resolve to ``posts/_post.html``.
    Records supply ``to_partial_path()`` and are assigned to the partial's
    basename (``post``). Explicit locals override that inferred assignment.
    """
    if template is not None and partial is not None:
        raise ValueError("Pass a template or partial, not both")
    record = None
    if template is not None and not isinstance(template, (str, list, tuple)):
        record = template
        partial = record.to_partial_path()
    elif partial is not None and not isinstance(partial, str):
        record = partial
        partial = record.to_partial_path()
    values = {}
    if partial is not None:
        template = _partial_template(partial)
        if record is not None:
            name = PurePosixPath(template).stem.removeprefix("_")
            values[name] = record
    if template is None:
        raise ValueError("A template, partial, or record is required")

    view = active_view.get()
    if view is not None:
        assigns = view._flaskteroids_assigns
    elif render_scope.get() is not None:
        assigns = render_assigns.get() or {}
    elif has_request_context():
        owner = getattr(g, "controller", None)
        assigns = vars(owner) if owner is not None else {}
    else:
        assigns = {}
    return Markup(
        render_template(template, **{**assigns, **values, **(locals or {}), **kwargs})
    )
