from flask import redirect
from flaskteroids import params
from flaskteroids.rules import rules
from flaskteroids.actions import skip_action
from app.controllers.concerns.authentication import Authentication
from app.models.user import User
from app.controllers.application_controller import ApplicationController
from app.mailers.passwords_mailer import PasswordsMailer


@rules(
    skip_action('_require_authentication', only=['new', 'create'])
)
class PasswordsController(ApplicationController):

    def new(self):
        pass

    def create(self):
        if user := User.find_by(**params.expect(['email_address'])):
            PasswordsMailer().reset(user).deliver_later()
        else:
            raise Exception('Try another email')


    def edit(self):
        pass


    def update(self):
        if self.user.update(**params.expect(['password', 'password_confirmation'])):
            return redirect('/login?notice=Password has been reset')
        else:
            return redirect(f'/passwords/edit?token={params["token"]}&alert=Passwords did not match')

    def _set_user_by_token(self):
        try:
            self.user = User.find_by_password_reset_token(params['token'])
        except:
            return redirect('/passwords/new?alert=Password reset link is invalid or has expired')

    def destroy(self):
        self._terminate_session()
        return redirect('/login')
