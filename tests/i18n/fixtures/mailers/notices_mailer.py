from flaskteroids.i18n import t
from flaskteroids.mailer import ActionMailer


class NoticesMailer(ActionMailer):
    def welcome(self, name):
        self.name = name
        return self.mail(
            to="reader@example.org",
            subject=t("notices_mailer.welcome.title", name=name),
        )
