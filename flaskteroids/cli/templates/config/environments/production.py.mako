import os


def configure(config):
    config.eager_load = True
    config.consider_all_requests_local = False
    config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000
    config.require_master_key = True
    config.mailer.perform_deliveries = True
    config.attachments.service = os.environ.get('FLASKTEROIDS_ATTACHMENTS_SERVICE', 'local')
    config.jobs.broker_url = os.environ.get(
        'CELERY_BROKER_URL', config.jobs.broker_url
    )
