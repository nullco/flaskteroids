from flask import request, abort
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature


class CSRFToken:

    def __init__(self, secret_key=None):
        self._serializer = URLSafeTimedSerializer(secret_key or '')
        self._salt = 'csrf-token'

    def generate(self):
        return self._serializer.dumps('csrf-token', salt=self._salt)

    def validate(self):
        if not self._should_validate():
            return
        token = request.form.get('csrf_token') or request.headers.get('X-CSRF-TOKEN')
        if not token:
            abort(400, 'Missing CSRF token.')
        try:
            self._serializer.loads(token, salt=self._salt, max_age=3600)
        except SignatureExpired:
            abort(400, 'CSRF token has expired.')
        except BadSignature:
            abort(400, 'Invalid CSRF token.')

    def _should_validate(self):
        return request.method not in ['GET', 'HEAD', 'OPTIONS', 'TRACE']
