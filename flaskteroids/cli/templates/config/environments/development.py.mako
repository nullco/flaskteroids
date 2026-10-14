def configure(config):
    config.enable_reloading = True
    config.consider_all_requests_local = True
    config.action_controller.perform_caching = False
    config.action_mailer.perform_deliveries = False
    config.attachments.service = 'local'
