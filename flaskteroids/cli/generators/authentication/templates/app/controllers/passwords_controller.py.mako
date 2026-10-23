from flask import url_for
from flaskteroids.actions import skip_before_action, before_action
from app.models.user import User
from app.controllers.application_controller import ApplicationController
from app.mailers.passwords_mailer import PasswordsMailer


class PasswordsController(ApplicationController):
    skip_before_action('_require_authentication')
    before_action('_set_user_by_token', only=['edit', 'update'])

    def new(self):
        pass

    def create(self):
        if user := User.find_by(**self.params.expect('email_address')):
            PasswordsMailer.with_(user=user).reset().deliver_later()

        return self.redirect_to(url_for('new_session'), notice='Password reset instructions sent (If user with that email address exists).')

    def edit(self):
        pass

    def update(self):
        if self.user.update(**self.params.expect('password', 'password_confirmation')):
            return self.redirect_to(url_for('new_session'), notice='Password has been reset')
        else:
            return self.redirect_to(url_for('edit_password', token=self.params["token"]), alert='Passwords did not match')

    def _set_user_by_token(self):
        try:
            self.user = User.find_by_password_reset_token(self.params['token'])
        except:
            return self.redirect_to(url_for('new_password'), alert='Password reset link is invalid or has expired')
