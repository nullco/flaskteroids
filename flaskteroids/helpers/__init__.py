import textwrap
from flask import url_for, current_app
from markupsafe import Markup
from flaskteroids.form import Form
from flaskteroids.csrf import CSRFToken


def button_to(message, instance, method):
    method = method.upper()
    name = instance.__class__.__name__.lower()
    url = '#'
    if method == 'DELETE':
        url = url_for(f"destroy_{name}", id=instance.id)
    return Markup(textwrap.dedent(f"""
        <form method="{method}" action="{url}">
            <input type="hidden" name="_method" value="delete" autocomplete="off">
            <input type="hidden" name="csrf_token" value="{csrf_token()}">
            <button type="submit">{message}</button>
        </form>
        """))


def form_with(model=None, caller=None, url='', method='POST'):
    prefix = None
    data = None
    if model:
        prefix = model.__class__.__name__.lower()
        url = url_for(f'create_{prefix}')
        if model.id:
            url = url_for(f'update_{prefix}', id=model.id)
            method = 'PUT'
        data = model.__json__()
    methods = ['GET', 'POST']
    form = Form(prefix, data)
    return textwrap.dedent(f"""
        <form action="{url}" method="{'POST' if method not in methods else method}">
           <input type="hidden" name="csrf_token" value="{csrf_token()}">
           <input type="hidden" name="_method" value="{method if method not in methods else ''}">
           {caller(form) if caller else ''}
        </form>
    """)


def csrf_token():
    return CSRFToken(current_app.config.get('SECRET_KEY')).generate()
