from flaskteroids.mailer import Mailer, helper


class NotesMailer(Mailer):
    helper("application", "admin/money")

    def welcome(self):
        self.title = "Newsletter"
        return self.mail(to="reader@example.com", subject="Welcome")


class PlainMailer(Mailer):
    def welcome(self):
        return self.mail(to="reader@example.com", subject="Plain")
