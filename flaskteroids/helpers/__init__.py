import textwrap

from flask import current_app, render_template, url_for
from markupsafe import Markup, escape

from flaskteroids._html import attributes, validate_url
from flaskteroids.assets import asset_path as asset_path
from flaskteroids.assets import stylesheet_link_tag as stylesheet_link_tag
from flaskteroids.csrf import CSRFToken
from flaskteroids.form import Form
from flaskteroids.inflector import inflector


def link_to(name, path, **kwargs):
    path = validate_url(path, link=True)
    attrs = attributes(kwargs)
    return Markup(f'<a href="{escape(path)}" {attrs}>{escape(name)}</a>')


def button_to(message, instance, method):
    method = method.upper()
    name = inflector.underscore(instance.__class__.__name__)
    url = "#"
    if method == "DELETE":
        url = url_for(f"destroy_{name}", id=instance.id)
    url = validate_url(url)
    return Markup(
        textwrap.dedent(f"""
        <form method="{escape(str(method))}" action="{escape(url)}">
            <input type="hidden" name="_method" value="delete" autocomplete="off">
            <input type="hidden" name="csrf_token" value="{escape(str(csrf_token()))}">
            <button type="submit">{escape(message)}</button>
        </form>
        """)
    )


def form_with(model=None, caller=None, url="", method="POST", multipart=False):
    prefix = None
    data = None
    if model:
        prefix = inflector.underscore(model.__class__.__name__)
        url = url_for(f"create_{prefix}")
        if model.id:
            url = url_for(f"update_{prefix}", id=model.id)
            method = "PUT"
        data = model._form_data()
    url = validate_url(url)
    methods = ["GET", "POST"]
    form = Form(prefix, data)
    body = caller(form) if caller else ""
    encoding = ' enctype="multipart/form-data"' if multipart or form.multipart else ""
    return textwrap.dedent(f"""
        <form action="{escape(url)}" method="{escape(str("POST" if method not in methods else method))}"{encoding}>
           <input type="hidden" name="csrf_token" value="{escape(str(csrf_token()))}">
           <input type="hidden" name="_method" value="{escape(str(method if method not in methods else ""))}">
           {body}
        </form>
    """)


def render(template, **kwargs):
    return Markup(render_template(template, **kwargs))


def csrf_token():
    return CSRFToken(current_app.config.get("SECRET_KEY")).generate()
