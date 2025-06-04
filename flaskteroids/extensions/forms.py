import textwrap
from markupsafe import Markup, escape
from flask import request, abort
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature


class FormsExtension:

    def __init__(self, app):
        self._serializer = URLSafeTimedSerializer("")
        self._salt = 'csrf-token'
        if app:
            self.init_app(app)

    def init_app(self, app):
        app.jinja_env.globals['form_with'] = self._form_with
        app.jinja_env.globals['csrf_token'] = self._generate_csrf_token
        secret_key = app.config.get('SECRET_KEY') or ''

        self._serializer = URLSafeTimedSerializer(secret_key)

        @app.before_request
        def _():
            if self._should_validate_csrf_token():
                self._validate_csrf_token()

        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["flaskteroids_forms"] = self

    def _generate_csrf_token(self):
        return self._serializer.dumps('csrf-token', salt=self._salt)

    def _validate_csrf_token(self):
        token = request.form.get('csrf_token') or request.headers.get('X-CSRF-TOKEN')
        if not token:
            abort(400, 'Missing CSRF token.')
        try:
            self._serializer.loads(token, salt=self._salt, max_age=3600)
        except SignatureExpired:
            abort(400, 'CSRF token has expired.')
        except BadSignature:
            abort(400, 'Invalid CSRF token.')

    def _should_validate_csrf_token(self):
        return request.method not in ['GET', 'HEAD', 'OPTIONS', 'TRACE']

    def _form_with(self, model=None, caller=None, url='', method='POST'):
        prefix = None
        data = None
        if model:
            prefix = model.__class__.__name__.lower()
            data = model.__json__()
        methods = ['GET', 'POST']
        form = Form(prefix, data)
        return textwrap.dedent(f"""
            <form action="{url}" method="{'POST' if method not in methods else method}">
               <input type="hidden" name="csrf_token" value="{self._generate_csrf_token()}">
               <input type="hidden" name="_method" value="{method if method not in methods else ''}">
               {caller(form) if caller else ''}
            </form>
        """)


class Form:

    def __init__(self, prefix: str | None, data: dict | None = None) -> None:
        self._prefix = prefix
        self._data = data or {}

    def _get_name(self, field):
        if not self._prefix:
            return field
        return f"{self._prefix}[{field}]"

    def _get_id(self, field):
        if not self._prefix:
            return field
        return f"{self._prefix}_{field}"

    def _get_value(self, field):
        if field not in self._data:
            return ''
        return escape(self._data.get(field))

    def label(self, field):
        return Markup(f'<label for="{self._get_id(field)}">{field.title()}</label>')

    def _input_type(self, type_, field, **kwargs):
        value = kwargs.pop('value', None)
        value = value if value is not None else self._get_value(field)
        attrs = {
            'type': type_,
            'id': self._get_id(field),
            'name': self._get_name(field),
            'value': value,
            **kwargs
        }
        attrs = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        return Markup(f'<input {attrs}>')

    def hidden_field(self, field, **kwargs):
        return self._input_type('hidden', field, **kwargs)

    def text_field(self, field, **kwargs):
        return self._input_type('text', field, **kwargs)

    def password_field(self, field, **kwargs):
        return self._input_type('password', field, **kwargs)

    def email_field(self, field, **kwargs):
        return self._input_type('email', field, **kwargs)

    def phone_field(self, field, **kwargs):
        return self._input_type('tel', field, **kwargs)

    def url_field(self, field, **kwargs):
        return self._input_type('url', field, **kwargs)

    def date_field(self, field, **kwargs):
        return self._input_type('date', field, **kwargs)

    def time_field(self, field, **kwargs):
        return self._input_type('time', field, **kwargs)

    def datetime_field(self, field, **kwargs):
        return self._input_type('datetime-local', field, **kwargs)

    def search_field(self, field, **kwargs):
        return self._input_type('search', field, **kwargs)

    def color_field(self, field, **kwargs):
        return self._input_type('color', field, **kwargs)

    def text_area(self, field, value=None):
        val = value if value is not None else self._get_value(field)
        return Markup(f'<textarea name="{self._get_name(field)}" id="{self._get_id(field)}" value="{val}"></textarea>')

    def submit(self, value='Submit'):
        return Markup(f'<input type="submit" value="{value}">')
