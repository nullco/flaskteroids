from jinja2 import Template
from markupsafe import Markup, escape

from flaskteroids._html import attributes


class Form:

    def __init__(self, prefix: str | None, data: dict | None = None) -> None:
        self._prefix = prefix
        self._data = data or {}
        self.multipart = False

    def _build_attributes(self, attrs):
        return attributes(attrs)

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
        return self._data[field]

    def label(self, field, **kwargs):
        attrs = self._build_attributes({'for': self._get_id(field), **kwargs})
        return Markup(f'<label {attrs}>{escape(str(field.title()))}</label>')

    def _input_type(self, type_, field, **kwargs):
        value = kwargs.pop('value', None)
        value = value if value is not None else self._get_value(field)
        attrs = self._build_attributes({
            'type': type_,
            'id': self._get_id(field),
            'name': self._get_name(field),
            'value': value,
            **kwargs
        })
        return Markup(f'<input {attrs}>')

    def hidden_field(self, field, *, multiple=False, **kwargs):
        if multiple:
            kwargs['name'] = self._get_name(field) + '[]'
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

    def file_field(self, field, *, multiple=False, include_hidden=True, **kwargs):
        self.multipart = True
        attrs = self._build_attributes({
            'type': 'file',
            'id': self._get_id(field),
            'name': self._get_name(field) + ('[]' if multiple else ''),
            **({'multiple': 'multiple'} if multiple else {}),
            **kwargs,
        })
        hidden = self.hidden_field(field, multiple=True, value='') if multiple and include_hidden else ''
        return Markup(f'{hidden}<input {attrs}>')

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
        val = escape(str(value if value is not None else self._get_value(field)))
        attrs = self._build_attributes({'name': self._get_name(field), 'id': self._get_id(field)})
        return Markup(f'<textarea {attrs}>{val}</textarea>')

    def collection_select(self, field, collection, option_value, option_display, prompt='Select one', value=None):
        value = str(value if value is not None else self._get_value(field))
        return Markup(Template("""
            <select id="{{ id|forceescape }}" name="{{ name|forceescape }}">
              <option value="">{{ prompt }}</option>
              {% for elem in collection %}
              <option value="{{ elem[option_value]|forceescape }}" {% if elem[option_value]|string == value %}selected{% endif %}>
                {{ elem[option_display] }}
              </option>
              {% endfor %}
            </select>
        """, autoescape=True).render(
            id=self._get_id(field),
            name=self._get_name(field),
            collection=collection,
            option_value=option_value,
            option_display=option_display,
            prompt=prompt,
            value=value
        ))

    def submit(self, value='Submit', **kwargs):
        attrs = self._build_attributes(kwargs)
        return Markup(f'<input type="submit" value="{escape(str(value))}" {attrs}>')
