from flaskteroids.form import Form
from tests.assertions import HTML


def test_file_field_renders_blank_value_for_existing_attachment():
    form = Form("user", {"avatar": "private-key"})
    source = str(form.file_field("avatar", accept="image/png"))
    html = HTML(source)
    field = next(attrs for tag, attrs in html.elements if attrs.get("type") == "file")

    assert html.has("input", type="file", name="user[avatar]", accept="image/png")
    assert "value" not in field
    assert "private-key" not in source
    assert form.multipart


def test_multiple_file_field_uses_array_names_and_hidden_blank():
    html = HTML(Form("user").file_field("photos", multiple=True))
    field = next(attrs for tag, attrs in html.elements if attrs.get("type") == "file")

    assert html.has("input", type="file", name="user[photos][]")
    assert "multiple" in field
    assert html.has("input", type="hidden", name="user[photos][]", value="")


def test_hidden_blank_can_be_disabled():
    html = HTML(Form("user").file_field("photos", multiple=True, include_hidden=False))

    assert html.has("input", type="file", name="user[photos][]")
    assert not html.has("input", type="hidden")


def test_file_field_escapes_attributes():
    payload = '" onfocus="alert(1)'
    html = HTML(Form("user").file_field("avatar", accept=payload))

    assert html.has("input", type="file", accept=payload)
    assert all("onfocus" not in attrs for _, attrs in html.elements)


def test_hidden_field_supports_retained_signed_blob_ids():
    html = HTML(Form("user").hidden_field("photos", value="signed-id", multiple=True))

    assert html.has("input", type="hidden", name="user[photos][]", value="signed-id")
