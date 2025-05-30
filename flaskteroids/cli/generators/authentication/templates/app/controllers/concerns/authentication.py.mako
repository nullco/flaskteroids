from flask import session, redirect, url_for
from flaskteroids.concern import Concern
from flaskteroids.rules import rules
from flaskteroids.actions import before_action
from flaskteroids.current import Current
from app.models.session import Session


@rules(
    before_action('_require_authentication')
)
class Authentication(Concern):

    def _is_authenticated(self):
        return bool(self._resume_session())

    def _require_authentication(self):
        if not self._is_authenticated():
            return self._request_authentication()

    def _resume_session(self):
        if not Current.session:
            Current.session = self._find_session_by_cookie()
        return Current.session

    def _request_authentication(self):
        return redirect(url_for('new_session'))

    def _find_session_by_cookie(self):
        if 'session_id' not in session:
            return
        return Session.find_by(id=session['session_id'])

    def _start_new_session_for(self, user):
        s = Session.create(user_id=user.id)
        session['session_id'] = s.id

    def _terminate_session(self):
        Current.session.destroy()
        session.clear()
