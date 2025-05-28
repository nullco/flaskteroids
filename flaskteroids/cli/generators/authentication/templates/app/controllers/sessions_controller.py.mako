from flask import redirect
from flaskteroids import params
from flaskteroids.rules import rules
from flaskteroids.actions import skip_action
from app.models.user import User
from app.controllers.application_controller import ApplicationController


@rules(
    skip_action('_require_authentication', only=['new', 'create'])
)
class SessionsController(ApplicationController):

    def new(self):
        pass

    def create(self):
        if user := User.authenticate_by(**params.expect(['email_address', 'password'])):
            self._start_new_session_for(user)
            return redirect('/')
        else:
            return redirect('/login?alert=Try another email address or password.')

    def destroy(self):
        self._terminate_session()
        return redirect('/login')

