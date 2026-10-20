from contextlib import contextmanager
from uuid import uuid4

from app.models.user import User

from tests.assertions import HTML


@contextmanager
def account(app):
    app.config.action_controller.allow_forgery_protection = True
    with app.app_context():
        user = User.create(
            email_address=f"{uuid4().hex}@example.com", password="secret"
        )
        assert user.is_persisted(), user.errors
        user_id = user.id
    try:
        yield user
    finally:
        with app.app_context():
            User.find(user_id).destroy()


def sign_in(client, user):
    response = client.get("/session/new")
    assert response.status_code == 200
    form = next(
        form for form in HTML(response.text).forms if "email_address" in form["fields"]
    )
    response = client.post(
        form["attributes"]["action"],
        data=form["fields"]
        | {"email_address": user.email_address, "password": "secret"},
    )
    assert response.status_code == 302, response.text
    return form["fields"]["csrf_token"]


def submit_form(client, response, action, **values):
    form = next(
        form
        for form in HTML(response.text).forms
        if form["attributes"].get("action") == action
    )
    return client.open(
        action, method=form["attributes"]["method"], data=form["fields"] | values
    )
