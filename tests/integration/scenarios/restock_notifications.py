"""Exercise the Getting Started subscription and mail examples in a real app."""

import json
from urllib.parse import urlsplit

from app.models.product import Product
from app.models.subscriber import Subscriber
from wsgi import app

from flaskteroids.mailer import MessageDeliveryJob
from tests.assertions import HTML
from tests.integration.scenarios.routing_support import submit_form

app.config["SERVER_NAME"] = "localhost"
app.config.action_controller.allow_forgery_protection = True
client = app.test_client()
with app.app_context():
    product = Product.create(name="T-Shirt", inventory_count=0)
    product_id = product.id
    other = Product.create(name="Already available", inventory_count=5)
    other_id = other.id

try:
    product_path = f"/products/{product_id}"
    collection = f"{product_path}/subscribers"
    page = client.get(product_path)
    assert page.status_code == 200
    rejected = submit_form(client, page, collection, **{"subscriber[email]": ""})
    assert rejected.status_code == 422
    assert HTML(rejected.text).has("input", name="subscriber[email]", value="")
    for email in ("reader@example.org", "reader@example.org", "second@example.org"):
        response = submit_form(client, page, collection, **{"subscriber[email]": email})
        assert response.status_code == 302

    with app.app_context():
        product = Product.find(product_id)
        queue = app.extensions["flaskteroids.jobs"].queue_adapter
        deliveries = app.extensions["flaskteroids.mail"].delivery_method.deliveries
        assert product.subscribers.all().count() == 2
        assert queue.enqueued_jobs == []
        assert not product.update(inventory_count=-1)
        assert queue.enqueued_jobs == []
        try:
            with Product.transaction():
                assert product.update(inventory_count=5)
                assert queue.enqueued_jobs == []
                raise RuntimeError("abort")
        except RuntimeError:
            pass
        assert queue.enqueued_jobs == []
        assert product.update(inventory_count=5)
        assert len(queue.enqueued_jobs) == 2
        assert deliveries == []
        payloads = json.loads(json.dumps([job.kwargs for job in queue.enqueued_jobs]))
        queue.clear()
        assert product.update(inventory_count=6)
        assert product.update(name="Renamed T-Shirt")
        reader = product.subscribers.where(email="reader@example.org").first()
        reader_id = reader.id
        assert reader.update(email="changed@example.org")
        assert queue.enqueued_jobs == []
        for payload in payloads:
            MessageDeliveryJob().perform(**payload)
        assert {message["To"] for message in deliveries} == {
            "reader@example.org",
            "second@example.org",
        }
        message = next(
            mail for mail in deliveries if mail["To"] == "reader@example.org"
        )
        assert message["Subject"] == "T-Shirt is back in stock"
        text = message.get_body(preferencelist=("plain",)).get_content()
        assert f"http://localhost{product_path}" in text
        unsubscribe_url = next(
            line.removeprefix("Unsubscribe: ")
            for line in text.splitlines()
            if line.startswith("Unsubscribe: ")
        )
        unsubscribe_path = urlsplit(unsubscribe_url).path

    confirmation = client.get(unsubscribe_path)
    assert confirmation.status_code == 200
    with app.app_context():
        assert Subscriber.find(reader_id).is_persisted()
    assert client.post(unsubscribe_path).status_code == 400
    assert submit_form(client, confirmation, unsubscribe_path).status_code == 302
    with app.app_context():
        assert Subscriber.find_by(id=reader_id) is None
        product = Product.find(product_id)
        assert product.update(inventory_count=0)
        assert product.update(inventory_count=5)
        assert len(queue.enqueued_jobs) == 1
        queue.perform_all()
        assert deliveries[-1]["To"] == "second@example.org"
finally:
    with app.app_context():
        for identity in (product_id, other_id):
            Product.find(identity).destroy()
