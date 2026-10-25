from flaskteroids.testing import TestDeliveryMethod, TestQueueAdapter


def configure(config):
    config.enable_reloading = False
    config.eager_load = False
    config["SERVER_NAME"] = "localhost"
    config.action_controller.perform_caching = False
    config.action_controller.allow_forgery_protection = True
    config.jobs.queue_adapter = TestQueueAdapter
    config.attachments.service = "test"
    config.action_mailer.delivery_method = TestDeliveryMethod
    config.action_mailer.perform_deliveries = True
