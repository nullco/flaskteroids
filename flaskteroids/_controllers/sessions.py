"""The stateless default for API-only applications."""

from flask.sessions import SessionInterface


class StatelessSessionInterface(SessionInterface):
    def open_session(self, app, request):
        return None
