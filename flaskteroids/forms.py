import textwrap
from markupsafe import Markup, escape
from flaskteroids.model import Model


def form_with(model: Model, caller):
    form = Form(model)
    # TODO: Implement support for CSRF tokens
    return textwrap.dedent(f"""
        <form action="{''}" method="POST">
           <input type="hidden" name="csrf_token" value="TBD">
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
