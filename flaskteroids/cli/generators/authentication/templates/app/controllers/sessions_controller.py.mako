from flask import redirect, url_for
from flaskteroids import params
from flaskteroids.rules import rules
from flaskteroids.actions import skip_action
from flaskteroids.rate_limit import rate_limit
from app.models.user import User
from app.controllers.application_controller import ApplicationController


@rules(
    skip_action('_require_authentication', only=['new', 'create']),
    rate_limit(to=10, within=3*60, only=['create'], with_=lambda: redirect(url_for('new_session', alert='Try again later')))
)
class SessionsController(ApplicationController):

    def new(self):
        pass

    def create(self):
        if user := User.authenticate_by(**params.expect(['email_address', 'password'])):
            self._start_new_session_for(user)
            return redirect(self._after_authentication_url())
        else:
            return redirect(url_for('new_session', alert='Try another email address or password.'))

    def destroy(self):
        self._terminate_session()
        return redirect(url_for('new_session'))
