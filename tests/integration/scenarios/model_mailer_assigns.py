"""Pass saved models from a web process to a separately booted mail worker."""

import json
import sys
from pathlib import Path

from app.mailers.product_mailer import ProductMailer
from app.models.product import Product
from app.models.subscriber import Subscriber
from wsgi import app

from flaskteroids.mailer import MessageDeliveryJob

mode, filename = sys.argv[1:]
payload = Path(filename)
app.config["SERVER_NAME"] = "localhost"
with app.app_context():
    if mode == "enqueue":
        product = Product.create(name="Original product", inventory_count=1)
        subscriber = Subscriber.create(product=product, email="reader@example.org")
        ProductMailer.with_(
            product=product, subscriber=subscriber
        ).in_stock().deliver_later()
        queue = app.extensions["flaskteroids.jobs"].queue_adapter
        payload.write_text(
            json.dumps({"product_id": product.id, "job": queue.enqueued_jobs[0].kwargs})
        )
        assert product.update(name="Updated product")
    else:
        assert mode == "deliver"
        data = json.loads(payload.read_text())
        try:
            MessageDeliveryJob().perform(**data["job"])
            message = app.extensions["flaskteroids.mail"].delivery_method.deliveries[0]
            assert message["Subject"] == "Original product is back in stock"
            text = message.get_body(preferencelist=("plain",)).get_content()
            assert "Updated product is back in stock" in text
            assert f"http://localhost/products/{data['product_id']}" in text
            assert "http://localhost/unsubscribe/" in text
        finally:
            Product.find(data["product_id"]).destroy()
