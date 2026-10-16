import pytest

from flaskteroids.form import Form
from tests.assertions import HTML


@pytest.mark.parametrize(
    "helper, field, value, input_type",
    [
        ("text_field", "name", None, "text"),
        ("number_field", "age", "30", "number"),
        ("password_field", "password", None, "password"),
        ("email_field", "email", "test@example.com", "email"),
        ("phone_field", "phone", None, "tel"),
        ("url_field", "website", "https://example.com", "url"),
        ("date_field", "birthdate", None, "date"),
        ("time_field", "appointment", None, "time"),
        ("datetime_field", "created_at", None, "datetime-local"),
        ("search_field", "query", None, "search"),
        ("color_field", "favorite_color", None, "color"),
        ("hidden_field", "csrf_token", "abcde", "hidden"),
    ],
)
def test_form_renders_prefixed_fields_and_values(helper, field, value, input_type):
    data = {"name": "John Doe"}
    form = Form(prefix="user", data=data)
    options = {} if value is None else {"value": value}
    html = HTML(getattr(form, helper)(field, **options))

    assert html.has(
        "input",
        type=input_type,
        id=f"user_{field}",
        name=f"user[{field}]",
        value=value if value is not None else data.get(field, ""),
    )


@pytest.mark.parametrize("prefix, field_id", [("user", "user_name"), (None, "name")])
def test_label_targets_field(prefix, field_id):
    html = HTML(Form(prefix=prefix).label("name"))

    assert html.has("label", **{"for": field_id})
    assert html.text == "Name"


def test_submit_renders_button_value():
    assert HTML(Form(prefix=None).submit("Create")).has(
        "input", type="submit", value="Create"
    )


def test_form_renders_unprefixed_fields_with_blank_values():
    html = HTML(Form(prefix=None).text_field("name"))

    assert html.has("input", type="text", id="name", name="name", value="")


@pytest.mark.parametrize(
    "data, value, expected",
    [
        ({"bio": "Existing text"}, None, "Existing text"),
        ({"bio": "Existing text"}, "Replacement text", "Replacement text"),
        ({"bio": "Existing text"}, "", ""),
        ({"bio": "Existing text"}, 0, "0"),
        ({"bio": None}, None, ""),
        ({}, None, ""),
        ({"bio": "First line\nSecond line"}, None, "First line\nSecond line"),
        ({"bio": "<b>Text</b> & more"}, None, "<b>Text</b> & more"),
        (
            {},
            '</textarea><script>alert("x")</script>',
            '</textarea><script>alert("x")</script>',
        ),
    ],
)
def test_text_area_renders_escaped_content_and_explicit_overrides(
    data, value, expected
):
    html = HTML(Form(prefix="user", data=data).text_area("bio", value=value))

    assert html.has("textarea", name="user[bio]", id="user_bio")
    assert html.text == expected


def test_text_area_renders_unprefixed_name_and_id():
    html = HTML(Form(prefix=None, data={"bio": "Existing text"}).text_area("bio"))

    assert html.has("textarea", name="bio", id="bio")
    assert html.text == "Existing text"


@pytest.mark.parametrize("checked", [False, True])
def test_checkbox_reflects_boolean_field_value(checked):
    html = HTML(Form(prefix="user", data={"terms": checked}).checkbox("terms"))
    checkbox = next(
        attrs
        for tag, attrs in html.elements
        if tag == "input" and attrs.get("type") == "checkbox"
    )

    assert ("checked" in checkbox) is checked


def test_collection_select_renders_choices_and_selected_value():
    form = Form(prefix="user", data={"country": "CA"})
    collection = [
        {"id": "US", "name": "United States"},
        {"id": "CA", "name": "Canada"},
    ]
    html = HTML(form.collection_select("country", collection, "id", "name"))
    options = {attrs["value"]: attrs for tag, attrs in html.elements if tag == "option"}

    assert html.has("select", id="user_country", name="user[country]")
    assert {"US", "CA"} <= options.keys()
    assert "selected" in options["CA"]
    assert "selected" not in options["US"]
    assert "Canada" in html.text and "United States" in html.text
