import os


def configure(config):
    config.eager_load = True
    config.consider_all_requests_local = False
    config.require_master_key = True
    config.action_mailer.perform_deliveries = True
    config.attachments.service = os.environ.get('ATTACHMENTS_SERVICE', 'local')
    config.active_job.broker_url = os.environ.get(
        'CELERY_BROKER_URL', config.active_job.broker_url
    )
