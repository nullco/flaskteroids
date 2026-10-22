from flask import url_for
from app.mailers.application_mailer import ApplicationMailer


class PasswordsMailer(ApplicationMailer):

    def reset(self):
        user = self.params['user']
        self.reset_url = url_for(
            'edit_password', token=user.password_reset_token, _external=True
        )
        return self.mail(subject='Reset your password', to=user.email_address)
