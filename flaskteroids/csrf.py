import hmac
import secrets

from flask import abort, current_app, request, session
from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer


class CSRFToken:
    def __init__(self, secret_key=None):
        self._serializer = URLSafeTimedSerializer(secret_key or "")
        self._salt = "csrf-token"

    def generate(self):
        if "csrf_nonce" not in session:
            session["csrf_nonce"] = secrets.token_urlsafe(32)
        return self._serializer.dumps(session["csrf_nonce"], salt=self._salt)

    def validate(self):
        if not self._should_validate():
            return
        token = request.form.get("csrf_token") or request.headers.get("X-CSRF-TOKEN")
        if not token:
            abort(400, "Missing CSRF token.")
        try:
            nonce = self._serializer.loads(token, salt=self._salt, max_age=3600)
        except SignatureExpired:
            abort(400, "CSRF token has expired.")
        except BadData:
            abort(400, "Invalid CSRF token.")
        expected = session.get("csrf_nonce")
        if (
            not isinstance(nonce, str)
            or not isinstance(expected, str)
            or not expected
            or not hmac.compare_digest(nonce.encode(), expected.encode())
        ):
            abort(400, "CSRF token does not match this session.")

    def _should_validate(self):
        config = getattr(current_app.config, "action_controller", None)
        if config and not config.allow_forgery_protection:
            return False
        return request.method not in ["GET", "HEAD", "OPTIONS", "TRACE"]
