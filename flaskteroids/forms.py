import textwrap
from markupsafe import Markup, escape
from flask import request, abort
from flaskteroids.model import Model
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature


_serializer = URLSafeTimedSerializer("")
_salt = 'csrf-token'


def init(app):
    app.jinja_env.globals['form_with'] = form_with
    app.jinja_env.globals['csrf_token'] = _generate_csrf_token
    secret_key = app.config.get('SECRET_KEY') or ''

    global _serializer
    _serializer = URLSafeTimedSerializer(secret_key)

    @app.before_request
    def _():
        if _should_validate_csrf_token():
            _validate_csrf_token()


def _generate_csrf_token():
    return _serializer.dumps('csrf-token', salt=_salt)


def _validate_csrf_token():
    token = request.form.get('csrf_token') or request.headers.get('X-CSRF-TOKEN')
    if not token:
        abort(400, 'Missing CSRF token.')
    try:
        _serializer.loads(token, salt=_salt, max_age=3600)
    except SignatureExpired:
        abort(400, 'CSRF token has expired.')
    except BadSignature:
        abort(400, 'Invalid CSRF token.')


def _should_validate_csrf_token():
    return request.method not in ['GET', 'HEAD', 'OPTIONS', 'TRACE']


def form_with(model: Model, caller):
    form = Form(model)
    return textwrap.dedent(f"""
        <form action="{''}" method="POST">
           <input type="hidden" name="csrf_token" value="{_generate_csrf_token()}">
           {caller(form)}
        </form>
    """)


class Form:

    def __init__(self, model: Model) -> None:
        self._model = model

    def _get_name(self, field):
        return f"{self._model.__class__.__name__.lower()}[{field}]"

    def _get_id(self, field):
        return f"{self._model.__class__.__name__.lower()}_{field}"

    def _get_value(self, field):
        return escape(getattr(self._model, field) if hasattr(self._model, field) else '')

    def label(self, field):
        return Markup(f'<label for="{self._get_id(field)}">{field.title()}</label>')

    def _input_type(self, type_, field):
        val = self._get_value(field)
        return Markup(f'<input type="{type_}" name="{self._get_name(field)}" id="{self._get_id(field)}" value="{val}">')

    def hidden_field(self, field):
        return self._input_type('hidden', field)

    def text_field(self, field):
        return self._input_type('text', field)

    def password_field(self, field):
        return self._input_type('password', field)

    def email_field(self, field):
        return self._input_type('email', field)

    def phone_field(self, field):
        return self._input_type('tel', field)

    def url_field(self, field):
        return self._input_type('url', field)

    def date_field(self, field):
        return self._input_type('date', field)

    def time_field(self, field):
        return self._input_type('time', field)

    def datetime_field(self, field):
        return self._input_type('datetime-local', field)

    def search_field(self, field):
        return self._input_type('search', field)

    def color_field(self, field):
        return self._input_type('color', field)

    def text_area(self, field):
        val = self._get_value(field)
        return Markup(f'<textarea name="{self._get_name(field)}" id="{self._get_id(field)}" value="{val}"></textarea>')

    def submit(self, value='Submit'):
        return Markup(f'<input type="submit" value="{value}">')
