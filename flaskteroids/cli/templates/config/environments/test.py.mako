from flaskteroids.testing import TestDeliveryMethod, TestQueueAdapter


def configure(config):
    config.enable_reloading = False
    config.eager_load = False
    config["SERVER_NAME"] = "localhost"
    config.controller.perform_caching = False
    config.controller.allow_forgery_protection = False
    config.jobs.queue_adapter = TestQueueAdapter
    config.attachments.service = 'test'
    config.mailer.delivery_method = TestDeliveryMethod
    config.mailer.perform_deliveries = True
