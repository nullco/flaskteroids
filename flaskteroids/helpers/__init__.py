from flask import current_app, render_template
from flask import url_for as url_for
from markupsafe import Markup, escape

from flaskteroids._html import attributes, validate_url
from flaskteroids._routing import HTTP_METHODS
from flaskteroids.assets import asset_path as asset_path
from flaskteroids.assets import stylesheet_link_tag as stylesheet_link_tag
from flaskteroids.csrf import CSRFToken
from flaskteroids.form import Form
from flaskteroids.inflector import inflector
from flaskteroids.routes import _model_destination, _polymorphic_path


def link_to(name, path, **kwargs):
    path = validate_url(path, link=True)
    attrs = attributes(kwargs)
    return Markup(f'<a href="{escape(path)}" {attrs}>{escape(name)}</a>')


def _hidden_field(name, value):
    attrs = attributes(
        {"type": "hidden", "name": name, "value": value, "autocomplete": "off"}
    )
    return f"<input {attrs}>"


def _form_open(url, method, *, form=None, multipart=False):
    attrs = dict(form or {})
    verb = str(method)
    if verb.upper() in HTTP_METHODS:
        verb = verb.upper()
    attrs["method"] = "GET" if verb == "GET" else "POST"
    if url is False:
        attrs.pop("action", None)
    else:
        attrs["action"] = validate_url(url)
    if multipart:
        attrs["enctype"] = "multipart/form-data"
    hidden = ""
    if verb not in {"GET", "POST"}:
        hidden += _hidden_field("_method", verb)
    if verb != "GET":
        hidden += _hidden_field("csrf_token", csrf_token())
    return f"<form {attributes(attrs)}>{hidden}"


def button_to(message, destination, *, method=None, form=None, **button_attrs):
    if isinstance(destination, str):
        url = destination
        inferred_method = "POST"
    else:
        target = _model_destination(destination)[-1]
        url = _polymorphic_path(destination)
        inferred_method = "PATCH" if target.is_persisted() else "POST"
    form_attrs = {"class": "button_to", **(form or {})}
    opening = _form_open(
        url, inferred_method if method is None else method, form=form_attrs
    )
    button_attrs["type"] = "submit"
    return Markup(
        f"{opening}<button {attributes(button_attrs)}>{escape(message)}</button></form>"
    )


def form_with(
    model=None, caller=None, *, url=None, method=None, scope=None, multipart=False
):
    target = _model_destination(model)[-1] if model is not None else None
    prefix = scope
    if target is not None and prefix is None:
        prefix = inflector.underscore(type(target).__name__)
    if url is None:
        url = _polymorphic_path(model) if target is not None else ""
    if method is None:
        method = "PATCH" if target is not None and target.is_persisted() else "POST"
    # Validate before invoking the caller, retaining explicit false/empty actions.
    if url is not False:
        url = validate_url(url)
    form = Form(prefix, target._form_data() if target is not None else None)
    body = caller(form) if caller else ""
    opening = _form_open(url, method, multipart=multipart or form.multipart)
    return Markup(f"{opening}{body}</form>")


def render(template, **kwargs):
    return Markup(render_template(template, **kwargs))


def csrf_token():
    return CSRFToken(current_app.config.get("SECRET_KEY")).generate()
