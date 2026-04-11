from app.mailers.application_mailer import ApplicationMailer


class PasswordsMailer(ApplicationMailer):

    def reset(self, user):
        self.user = user
        return self.mail(subject='Reset your password', to=user.email_address)
