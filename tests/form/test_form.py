from flaskteroids.form import Form


def test_form_fields():
    form = Form(prefix="user", data={"name": "John Doe"})

    assert str(form.label("name")) == '<label for="user_name">Name</label>'
    assert str(form.text_field("name")) == '<input type="text" id="user_name" name="user[name]" value="John Doe">'
    assert str(form.number_field("age", value="30")) == '<input type="number" id="user_age" name="user[age]" value="30">'
    assert str(form.password_field("password")) == '<input type="password" id="user_password" name="user[password]" value="">'
    assert str(form.email_field("email", value="test@example.com")) == '<input type="email" id="user_email" name="user[email]" value="test@example.com">'
    assert str(form.phone_field("phone")) == '<input type="tel" id="user_phone" name="user[phone]" value="">'
    assert str(form.url_field("website", value="https://example.com")) == '<input type="url" id="user_website" name="user[website]" value="https://example.com">'
    assert str(form.date_field("birthdate")) == '<input type="date" id="user_birthdate" name="user[birthdate]" value="">'
    assert str(form.time_field("appointment")) == '<input type="time" id="user_appointment" name="user[appointment]" value="">'
    assert str(form.datetime_field("created_at")) == '<input type="datetime-local" id="user_created_at" name="user[created_at]" value="">'
    assert str(form.search_field("query")) == '<input type="search" id="user_query" name="user[query]" value="">'
    assert str(form.color_field("favorite_color")) == '<input type="color" id="user_favorite_color" name="user[favorite_color]" value="">'
    assert str(form.hidden_field("csrf_token", value="abcde")) == '<input type="hidden" id="user_csrf_token" name="user[csrf_token]" value="abcde">'
    assert str(form.text_area("bio")) == '<textarea name="user[bio]" id="user_bio" value=""></textarea>'
    assert 'type="checkbox"' in str(form.checkbox("terms"))
    assert str(form.submit("Create")) == '<input type="submit" value="Create" >'


def test_form_without_prefix_or_data():
    form = Form(prefix=None)

    assert str(form.label("name")) == '<label for="name">Name</label>'
    assert str(form.text_field("name")) == '<input type="text" id="name" name="name" value="">'


def test_checkbox():
    form_checked = Form(prefix="user", data={"terms": True})
    assert 'checked' in str(form_checked.checkbox("terms"))

    form_unchecked = Form(prefix="user", data={"terms": False})
    assert 'checked' not in str(form_unchecked.checkbox("terms"))


def test_collection_select():
    form = Form(prefix="user", data={"country": "CA"})
    collection = [
        {"id": "US", "name": "United States"},
        {"id": "CA", "name": "Canada"},
    ]

    select_html = str(form.collection_select("country", collection, "id", "name"))
    assert '<select id="user_country" name="user[country]">' in select_html
    assert '<option value="US" >' in select_html
    assert '<option value="CA" selected>' in select_html
    assert 'Canada' in select_html
    assert 'United States' in select_html
