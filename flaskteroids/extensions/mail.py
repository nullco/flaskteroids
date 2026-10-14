from flaskteroids.discovery import discover_classes
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.mailer import ActionMailer, init


class MailExtension:
    def __init__(self, app=None):
        self.delivery_method = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        if vars(self).get("_app", app) is not app:
            raise ProgrammerError(
                "A mail extension cannot be shared between applications."
            )
        if "flaskteroids.mail" in app.extensions:
            return
        config = app.config.action_mailer
        self.delivery_method = config.delivery_method(app, config)
        self._mailers = discover_classes(app.config.paths.mailers, ActionMailer)

        for mailer_class in self._mailers.values():
            init(mailer_class)

        self._app = app
        app.extensions["flaskteroids.mail"] = self

    def deliver(self, message):
        return self.delivery_method.deliver(message)
