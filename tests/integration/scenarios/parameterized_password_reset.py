"""Deliver a generated password reset mail without retaining the HTTP request."""

import json
from urllib.parse import urlsplit

from wsgi import app

from flaskteroids.mailer import MessageDeliveryJob
from tests.assertions import HTML
from tests.integration.scenarios.routing_support import account, submit_form

with account(app) as user:
    client = app.test_client()
    response = client.get("/passwords/new")
    assert response.status_code == 200
    form = next(
        form for form in HTML(response.text).forms if "email_address" in form["fields"]
    )
    created = submit_form(
        client,
        response,
        form["attributes"]["action"],
        email_address=user.email_address,
    )
    assert created.status_code == 302
    with app.app_context():
        queue = app.extensions["flaskteroids.jobs"].queue_adapter
        deliveries = app.extensions["flaskteroids.mail"].delivery_method.deliveries
        assert len(queue.enqueued_jobs) == 1
        assert deliveries == []
        payload = json.loads(json.dumps(queue.enqueued_jobs[0].kwargs))
        queue.clear()
        MessageDeliveryJob().perform(**payload)
        message = deliveries[0]
        assert message["To"] == user.email_address
        text = message.get_body(preferencelist=("plain",)).get_content()
        reset_url = next(line for line in text.splitlines() if line.startswith("http"))
        assert urlsplit(reset_url).netloc == "localhost"
        assert reset_url in message.get_body(preferencelist=("html",)).get_content()
    assert client.get(urlsplit(reset_url).path).status_code == 200
