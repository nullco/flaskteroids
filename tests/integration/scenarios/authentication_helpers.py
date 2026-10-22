"""Generated authentication helpers on public pages, with normal login and logout."""

from urllib.parse import urlsplit

from app.models.session import Session
from wsgi import app

from tests.assertions import HTML
from tests.integration.scenarios.routing_support import account, sign_in, submit_form


def assert_catalog(client, *, authenticated):
    response = client.get("/catalog")
    assert response.status_code == 200, response.text
    html = HTML(response.text)
    assert html.has("a", href="/session/new") is not authenticated
    assert any(form["fields"].get("_method") == "DELETE" for form in html.forms) is (
        authenticated
    )
    return response


def assert_requires_login(client):
    response = client.get("/catalog/edit")
    assert response.status_code == 302
    assert urlsplit(response.location).path == "/session/new"


with account(app) as user:
    client = app.test_client()
    assert_catalog(client, authenticated=False)
    assert_requires_login(client)

    sign_in(client, user)
    assert client.get("/catalog/edit").text == "Catalog editor"
    page = assert_catalog(client, authenticated=True)

    logout = submit_form(client, page, "/session")
    assert logout.status_code == 302
    assert_catalog(client, authenticated=False)
    assert_requires_login(client)

    sign_in(client, user)
    with app.app_context():
        Session.find_by(user_id=user.id).destroy()
    assert_catalog(client, authenticated=False)
    assert_requires_login(client)

    with client.session_transaction() as browser_session:
        browser_session["session_id"] = -1
    assert_catalog(client, authenticated=False)
    assert_requires_login(client)
