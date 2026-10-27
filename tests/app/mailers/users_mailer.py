from flaskteroids.mailer import Mailer


class UsersMailer(Mailer):
    def welcome_email(self):
        return self.mail(to="example.org", subject="Welcome!")
