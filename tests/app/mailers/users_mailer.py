from flaskteroids.mailer import ActionMailer


class UsersMailer(ActionMailer):
    def welcome_email(self):
        return self.mail(to='example.org', subject='Welcome!')
