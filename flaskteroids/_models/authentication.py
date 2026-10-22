from __future__ import annotations

import hmac
from collections.abc import Callable
from typing import TYPE_CHECKING, Self

from flask import current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from flaskteroids._models.validation import validates
from flaskteroids.declarations import model_for
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.rules import declaration

if TYPE_CHECKING:
    from flaskteroids.model import Model


def _password_reset_serializer(
    model_cls: type[Model], pwname: str
) -> URLSafeTimedSerializer:
    salt = f"pwres:{model_cls.__module__}.{model_cls.__qualname__}:{pwname}"
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=salt)


def _password_reset_fingerprint(
    serializer: URLSafeTimedSerializer, password_digest: str
) -> str:
    return hmac.new(
        serializer.secret_key, f"pwres:{password_digest}".encode(), "sha256"
    ).hexdigest()


class PasswordAuthenticator:
    @classmethod
    def authenticate_by(cls, **kwargs) -> Self | None:
        pwname = model_for(cls).password_field
        if not pwname:
            return
        password = kwargs.pop(pwname)
        entry = cls.find_by(**kwargs)
        if not entry:
            check_password_hash("a", "b")  # To protect against timing attacks
            return None
        if not entry.authenticate(password):
            return None
        return entry

    @classmethod
    def find_by_password_reset_token(cls, token: str) -> Self:
        pwname = model_for(cls).password_field
        if not pwname:
            raise ProgrammerError(
                "Password reset tokens require has_secure_password()."
            )
        serializer = _password_reset_serializer(cls, pwname)
        payload = serializer.loads(token, max_age=900)
        if (
            not isinstance(payload, dict)
            or type(payload.get("id")) is not int
            or not isinstance(payload.get("fingerprint"), str)
            or not payload["fingerprint"].isascii()
        ):
            raise BadSignature("Invalid password reset token.")
        entry = cls.find(payload["id"])
        fingerprint = _password_reset_fingerprint(
            serializer, entry.read_published_attribute(f"{pwname}_digest")
        )
        if not hmac.compare_digest(payload["fingerprint"], fingerprint):
            raise BadSignature("Password reset token has been invalidated.")
        return entry

    def authenticate(self, password: str) -> bool:
        pwname = model_for(self.__class__).password_field
        if not pwname:
            return False
        password_digest = self.read_published_attribute(f"{pwname}_digest")
        return bool(password_digest) and check_password_hash(password_digest, password)


@declaration
def has_secure_password(pwname: str = "password") -> Callable[[type[Model]], None]:
    length = validates(pwname, length={"minimum": 1, "maximum": 72})
    confirmation = validates(pwname, confirmation=True)

    def bind(cls: type[Model]) -> None:
        definition = model_for(cls)
        definition.password_field = pwname
        virtual_fields = definition.virtual_fields

        def _set_password_digest(self):
            value = getattr(self, f"{pwname}")
            setattr(self, f"{pwname}_digest", generate_password_hash(value))

        virtual_fields[pwname] = {"set_fn": _set_password_digest}

        def _set_password_reset_token(self):
            serializer = _password_reset_serializer(self.__class__, pwname)
            fingerprint = _password_reset_fingerprint(
                serializer, self.read_published_attribute(f"{pwname}_digest")
            )
            token = serializer.dumps({"id": self.id, "fingerprint": fingerprint})
            self._virtual_fields[f"{pwname}_reset_token"] = token

        virtual_fields[f"{pwname}_reset_token"] = {
            "read_only": True,
            "cache": False,
            "set_fn": _set_password_reset_token,
        }

        length(cls)
        confirmation(cls)

    return bind
