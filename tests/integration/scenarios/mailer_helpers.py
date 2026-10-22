"""Serialize queued mail and deliver it in a separately booted worker process."""

import json
import sys
from pathlib import Path

from app.mailers.catalog_mailer import CatalogMailer
from wsgi import app

from flaskteroids.mailer import MessageDeliveryJob

mode, filename = sys.argv[1:]
payload = Path(filename)
with app.app_context():
    if mode == "enqueue":
        CatalogMailer().notice().deliver_later()
        queue = app.extensions["flaskteroids.jobs"].queue_adapter
        payload.write_text(json.dumps(queue.enqueued_jobs[0].kwargs))
    else:
        assert mode == "deliver"
        MessageDeliveryJob().perform(**json.loads(payload.read_text()))
        delivered = app.extensions["flaskteroids.mail"].delivery_method.deliveries[-1]
        assert delivered.get_body(preferencelist=("html",)).get_content().strip() == (
            "Store|News: Catalog for readers!|False"
        )
