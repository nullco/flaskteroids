def configure(config):
    config.enable_reloading = True
    config.consider_all_requests_local = True
    config.controller.perform_caching = False
    config.mailer.perform_deliveries = False
    config.attachments.service = 'local'
