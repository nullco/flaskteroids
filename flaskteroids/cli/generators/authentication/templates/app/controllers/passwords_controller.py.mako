from flask import url_for
from flaskteroids import params, rules, redirect_to
from flaskteroids.actions import skip_before_action, before_action
from app.models.user import User
from app.controllers.application_controller import ApplicationController
from app.mailers.passwords_mailer import PasswordsMailer


@rules(
    skip_before_action('_require_authentication'),
    before_action('_set_user_by_token', only=['edit', 'update'])
)
class PasswordsController(ApplicationController):

    def new(self):
        pass

    def create(self):
        if user := User.find_by(**params.expect(['email_address'])):
            PasswordsMailer().reset(user).deliver_later()

        return redirect_to(url_for('new_session'), notice='Password reset instructions sent (If user with that email address exists).')

    def edit(self):
        pass

    def update(self):
        if self.user.update(**params.expect(['password', 'password_confirmation'])):
            return redirect_to(url_for('new_session'), notice='Password has been reset')
        else:
            return redirect_to(url_for('edit_password', token=params["token"]), alert='Passwords did not match')

    def _set_user_by_token(self):
        try:
            self.user = User.find_by_password_reset_token(params['token'])
        except:
            return redirect_to(url_for('new_password'), alert='Password reset link is invalid or has expired')
