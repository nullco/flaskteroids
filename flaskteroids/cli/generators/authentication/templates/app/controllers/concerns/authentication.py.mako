from flask import request, session, url_for
from flaskteroids import redirect_to, rules
from flaskteroids.concern import Concern
from flaskteroids.actions import before_action
from flaskteroids.current import current
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
        if not current.session:
            current.session = self._find_session_by_cookie()
        return current.session

    def _find_session_by_cookie(self):
        if 'session_id' not in session:
            return
        return Session.find_by(id=session['session_id'])

    def _request_authentication(self):
        session['return_to_after_authenticating'] = request.url
        return redirect_to(url_for('new_session'))

    def _after_authentication_url(self):
        return session.pop('return_to_after_authenticating', None) or url_for('root')

    def _start_new_session_for(self, user):
        s = Session.create(
            user_id=user.id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        session['session_id'] = s.id

    def _terminate_session(self):
        current.session.destroy()
        session.clear()
