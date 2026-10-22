from flaskteroids.mailer import ActionMailer, helper


class NotesMailer(ActionMailer):
    helper("application", "admin/money")

    def welcome(self):
        self.title = "Newsletter"
        return self.mail(to="reader@example.com", subject="Welcome")


class PlainMailer(ActionMailer):
    def welcome(self):
        return self.mail(to="reader@example.com", subject="Plain")
