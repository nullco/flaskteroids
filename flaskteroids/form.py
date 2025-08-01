from markupsafe import Markup, escape


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
        if field not in self._data or self._data[field] is None:
            return ''
        return escape(self._data.get(field))

    def label(self, field, **kwargs):
        attrs = {
            'for': self._get_id(field),
            **kwargs
        }
        attrs = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        return Markup(f'<label {attrs}>{field.title()}</label>')

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

    def number_field(self, field, **kwargs):
        return self._input_type('number', field, **kwargs)

    def checkbox(self, field, **_):
        attrs = {
            'checked': bool(self._data.get(field))
        }
        attrs = {k: k for k, v in attrs.items() if v}
        checkbox = f"""
        {self._input_type('hidden', field, value='0')}
        {self._input_type('checkbox', field, value='1', **attrs)}
        """
        return Markup(checkbox)

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
