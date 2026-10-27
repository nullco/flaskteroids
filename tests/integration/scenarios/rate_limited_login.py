"""Exercise the generated authentication controller's instance-bound limit handler."""

from wsgi import app

from tests.assertions import HTML
from tests.integration.scenarios.routing_support import submit_form

app.config.controller.allow_forgery_protection = True
client = app.test_client()
page = client.get("/session/new")
assert page.status_code == 200
for _ in range(11):
    response = submit_form(
        client,
        page,
        "/session",
        email_address="missing@example.org",
        password="incorrect",
    )
    assert response.status_code == 302
    page = client.get(response.headers["Location"])
    assert page.status_code == 200
assert "Try again later" in HTML(page.text).text
