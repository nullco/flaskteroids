import math
import time

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeSerializer


def signed_token(purpose, payload, expires_in=None):
    if expires_in is not None and (
        type(expires_in) not in (int, float) or not math.isfinite(expires_in)
    ):
        raise ValueError("expires_in must be a finite number of seconds or None")
    expiration = None if expires_in is None else time.time() + expires_in
    serializer = URLSafeSerializer(
        current_app.secret_key, salt=f"attachments:{purpose}"
    )
    return serializer.dumps({**payload, "expires_at": expiration})


def verified_token(purpose, token):
    serializer = URLSafeSerializer(
        current_app.secret_key, salt=f"attachments:{purpose}"
    )
    payload = serializer.loads(token)
    if not isinstance(payload, dict):
        raise BadSignature("Invalid attachment token")
    expiration = payload.get("expires_at")
    if expiration is not None:
        if type(expiration) not in (int, float) or not math.isfinite(expiration):
            raise BadSignature("Invalid attachment expiration")
        if time.time() > expiration:
            raise SignatureExpired("The attachment token has expired")
    return payload
