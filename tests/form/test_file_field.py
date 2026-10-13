from flaskteroids.form import Form


def test_file_field_never_renders_existing_value():
    form = Form("user", {"avatar": "private-key"})
    html = str(form.file_field("avatar", accept="image/png"))
    assert 'type="file"' in html
    assert 'name="user[avatar]"' in html
    assert 'accept="image/png"' in html
    assert "value=" not in html
    assert "private-key" not in html
    assert form.multipart


def test_multiple_file_field_uses_array_names_and_hidden_blank():
    html = str(Form("user").file_field("photos", multiple=True))
    assert html.count('name="user[photos][]"') == 2
    assert 'type="hidden"' in html
    assert 'multiple="multiple"' in html
    assert 'value=""' in html


def test_hidden_blank_can_be_disabled():
    html = str(Form("user").file_field("photos", multiple=True, include_hidden=False))
    assert 'type="hidden"' not in html


def test_file_field_escapes_attributes():
    html = str(Form("user").file_field("avatar", accept='" onfocus="alert(1)'))
    assert 'accept="&#34; onfocus=&#34;alert(1)"' in html


def test_hidden_field_supports_retained_signed_blob_ids():
    html = str(Form("user").hidden_field("photos", value="signed-id", multiple=True))
    assert 'name="user[photos][]"' in html
    assert 'value="signed-id"' in html
