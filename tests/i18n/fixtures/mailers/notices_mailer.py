from flaskteroids.i18n import t
from flaskteroids.mailer import Mailer


class NoticesMailer(Mailer):
    def welcome(self, name):
        self.name = name
        return self.mail(
            to="reader@example.org",
            subject=t("notices_mailer.welcome.title", name=name),
        )
