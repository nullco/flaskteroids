import re

from jinja2 import Template
from markupsafe import Markup, escape

from flaskteroids._html import attributes
from flaskteroids._models.errors import Errors
from flaskteroids.declarations import model_for
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.rich_text.content import Content
from flaskteroids.rich_text.extension import upload_attributes
from flaskteroids.rich_text.record import RichText


class Form:
    def __init__(
        self, prefix: str | None, data: dict | None = None, *, model=None
    ) -> None:
        self._prefix = prefix
        self._data = data or {}
        self._model = model
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
        prefix = re.sub(r"[\[\]]+", "_", self._prefix).rstrip("_")
        return f"{prefix}_{field}"

    def _get_value(self, field):
        if field not in self._data or self._data[field] is None:
            return ""
        return self._data[field]

    @property
    def model(self):
        return self._model

    @property
    def errors(self):
        return self._model.errors if self._model is not None else Errors()

    def fields_for(self, name, caller=None, *, include_id=True):
        if self._model is None:
            raise ProgrammerError("fields_for requires a model-backed form.")
        definition = model_for(type(self._model))
        if name not in definition.nested_attributes:
            raise ProgrammerError(
                f"Declare accepts_nested_attributes_for({name!r}) first."
            )
        association = definition.associations[name]
        value = getattr(self._model, name)
        collection = association.kind == "has_many"
        records = list(value) if collection else ([] if value is None else [value])
        output = []
        for index, record in enumerate(records):
            prefix = self._get_name(f"{name}_attributes")
            if collection:
                prefix += f"[{index}]"
            child = Form(
                prefix,
                record._form_data() | {"_destroy": record.marked_for_destruction()},
                model=record,
            )
            body = caller(child) if caller else ""
            hidden = (
                child.hidden_field("id") if include_id and record.is_persisted() else ""
            )
            self.multipart = self.multipart or child.multipart
            output.append(Markup(f"{body}{hidden}"))
        return Markup("").join(output)

    def label(self, field, **kwargs):
        attrs = self._build_attributes({"for": self._get_id(field), **kwargs})
        return Markup(f"<label {attrs}>{escape(str(field.title()))}</label>")

    def _input_type(self, type_, field, **kwargs):
        value = kwargs.pop("value", None)
        value = value if value is not None else self._get_value(field)
        attrs = self._build_attributes(
            {
                "type": type_,
                "id": self._get_id(field),
                "name": self._get_name(field),
                "value": value,
                **kwargs,
            }
        )
        return Markup(f"<input {attrs}>")

    def hidden_field(self, field, *, multiple=False, **kwargs):
        if multiple:
            kwargs["name"] = self._get_name(field) + "[]"
        return self._input_type("hidden", field, **kwargs)

    def text_field(self, field, **kwargs):
        return self._input_type("text", field, **kwargs)

    def number_field(self, field, **kwargs):
        return self._input_type("number", field, **kwargs)

    def checkbox(self, field, **_):
        attrs = {"checked": bool(self._data.get(field))}
        attrs = {k: k for k, v in attrs.items() if v}
        checkbox = f"""
        {self._input_type("hidden", field, value="0")}
        {self._input_type("checkbox", field, value="1", **attrs)}
        """
        return Markup(checkbox)

    def file_field(self, field, *, multiple=False, include_hidden=True, **kwargs):
        self.multipart = True
        attrs = self._build_attributes(
            {
                "type": "file",
                "id": self._get_id(field),
                "name": self._get_name(field) + ("[]" if multiple else ""),
                **({"multiple": "multiple"} if multiple else {}),
                **kwargs,
            }
        )
        hidden = (
            self.hidden_field(field, multiple=True, value="")
            if multiple and include_hidden
            else ""
        )
        return Markup(f"{hidden}<input {attrs}>")

    def password_field(self, field, **kwargs):
        return self._input_type("password", field, **kwargs)

    def email_field(self, field, **kwargs):
        return self._input_type("email", field, **kwargs)

    def phone_field(self, field, **kwargs):
        return self._input_type("tel", field, **kwargs)

    def url_field(self, field, **kwargs):
        return self._input_type("url", field, **kwargs)

    def date_field(self, field, **kwargs):
        return self._input_type("date", field, **kwargs)

    def time_field(self, field, **kwargs):
        return self._input_type("time", field, **kwargs)

    def datetime_field(self, field, **kwargs):
        return self._input_type("datetime-local", field, **kwargs)

    def search_field(self, field, **kwargs):
        return self._input_type("search", field, **kwargs)

    def color_field(self, field, **kwargs):
        return self._input_type("color", field, **kwargs)

    def text_area(self, field, value=None):
        val = escape(str(value if value is not None else self._get_value(field)))
        attrs = self._build_attributes(
            {"name": self._get_name(field), "id": self._get_id(field)}
        )
        return Markup(f"<textarea {attrs}>{val}</textarea>")

    def rich_text_area(self, field, *, value=None, **kwargs):
        if value is None:
            value = (
                getattr(self._model, field).body
                if self._model is not None
                and field in model_for(type(self._model)).rich_texts
                else self._get_value(field)
            )
        if isinstance(value, RichText):
            value = value.body
        content = value if isinstance(value, Content) else Content(str(value))
        editor_id = kwargs.pop("id", self._get_id(field))
        attrs = self._build_attributes(
            {
                **kwargs,
                **(
                    upload_attributes(self._model, field)
                    if self._model is not None
                    else {"attachments": "false"}
                ),
                "id": editor_id,
                "name": self._get_name(field),
                "value": content.to_editor_html(),
                "class": kwargs.get("class", "lexxy-content"),
                "data-flaskteroids-rich-text": "",
            }
        )
        return Markup(f"<lexxy-editor {attrs}></lexxy-editor>")

    def collection_select(
        self,
        field,
        collection,
        option_value,
        option_display,
        prompt="Select one",
        value=None,
    ):
        value = str(value if value is not None else self._get_value(field))
        return Markup(
            Template(
                """
            <select id="{{ id|forceescape }}" name="{{ name|forceescape }}">
              <option value="">{{ prompt }}</option>
              {% for elem in collection %}
              <option value="{{ elem[option_value]|forceescape }}" {% if elem[option_value]|string == value %}selected{% endif %}>
                {{ elem[option_display] }}
              </option>
              {% endfor %}
            </select>
        """,
                autoescape=True,
            ).render(
                id=self._get_id(field),
                name=self._get_name(field),
                collection=collection,
                option_value=option_value,
                option_display=option_display,
                prompt=prompt,
                value=value,
            )
        )

    def submit(self, value="Submit", **kwargs):
        attrs = self._build_attributes(kwargs)
        return Markup(f'<input type="submit" value="{escape(str(value))}" {attrs}>')
