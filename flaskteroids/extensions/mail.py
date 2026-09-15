from flaskteroids.discovery import discover_classes
from flaskteroids.mailer import ActionMailer, init
import flaskteroids.registry as registry


class MailExtension:
    def __init__(self, app=None):
        self.delivery_method = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        config = app.config.action_mailer
        self.delivery_method = config.delivery_method(app, config)
        self._mailers = discover_classes(app.config.paths.mailers, ActionMailer)

        for mailer_name, mailer_class in self._mailers.items():
            ns = registry.get(mailer_class)
            ns["name"] = mailer_name
            init(mailer_class)

        app.extensions["flaskteroids.mail"] = self

    def deliver(self, message):
        return self.delivery_method.deliver(message)
