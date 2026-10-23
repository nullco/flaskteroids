"""Application-level attribute encryption shared by models and rich text."""

import base64
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, AESSIV
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from flask import current_app

from flaskteroids.exceptions import EncryptionError

_PREFIX = "flaskteroids:encrypted:v1:"


def generate_encryption_key():
    """Return a dedicated, base64-encoded 32-byte encryption key."""
    return base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode()


def is_encrypted(source):
    return isinstance(source, str) and source.startswith(_PREFIX)


def _keys(deterministic):
    name = "deterministic_key" if deterministic else "primary_key"
    value = getattr(current_app.config.active_record.encryption, name)
    if value is None:
        value = os.environ.get(f"ACTIVE_RECORD_ENCRYPTION_{name.upper()}")
    if value is None:
        credentials = getattr(current_app, "credentials", None)
        configured = (
            credentials.to_dict().get("active_record_encryption", {})
            if credentials is not None
            else {}
        )
        if not isinstance(configured, dict):
            raise EncryptionError(
                "active_record_encryption credentials must be a mapping"
            )
        value = configured.get(name)
    values = value if isinstance(value, (list, tuple)) else [value]
    if deterministic and isinstance(value, (list, tuple)):
        raise EncryptionError("deterministic_key must be a single, stable key")
    if not values or any(not isinstance(value, str) for value in values):
        raise EncryptionError(
            f"Configure active_record.encryption.{name} or "
            f"active_record_encryption.{name} credentials. "
            "Generate dedicated keys with flask db:encryption:init."
        )
    keys = []
    for value in values:
        try:
            key = base64.b64decode(value, altchars=b"-_", validate=True)
        except (ValueError, TypeError) as error:
            raise EncryptionError("Invalid attribute encryption key") from error
        if len(key) != 32:
            raise EncryptionError("Attribute encryption keys must contain 32 bytes")
        keys.append(key)
    return keys


def _aad(context, deterministic):
    return json.dumps([_PREFIX, context, deterministic], separators=(",", ":")).encode()


def _siv(key):
    material = HKDF(
        algorithm=hashes.SHA256(),
        length=64,
        salt=None,
        info=b"flaskteroids:attribute-encryption:aes-256-siv:v1",
    ).derive(key)
    return AESSIV(material)


def encrypt(source, *, context, deterministic=False):
    if source is None:
        return None
    key = _keys(deterministic)[-1]
    aad = _aad(context, deterministic)
    try:
        plaintext = source.encode("utf-8")
    except UnicodeEncodeError as error:
        raise EncryptionError("Encrypted attributes require valid UTF-8") from error
    if deterministic:
        mode, payload = "siv", _siv(key).encrypt(plaintext, [aad])
    else:
        nonce = os.urandom(12)
        mode = "gcm"
        payload = nonce + AESGCM(key).encrypt(nonce, plaintext, aad)
    return _PREFIX + mode + ":" + base64.urlsafe_b64encode(payload).decode()


def decrypt(source, *, context, deterministic=False):
    if source is None:
        return None
    if not is_encrypted(source):
        if isinstance(source, str) and not source.startswith("flaskteroids:encrypted:"):
            if (
                current_app.config.active_record.encryption.support_unencrypted_data
                is True
            ):
                return source
        raise EncryptionError("Expected an encrypted attribute envelope")
    try:
        mode, encoded = source[len(_PREFIX) :].split(":", 1)
        if mode != ("siv" if deterministic else "gcm"):
            raise EncryptionError("Unexpected attribute encryption scheme")
        payload = base64.b64decode(encoded, altchars=b"-_", validate=True)
    except (ValueError, TypeError) as error:
        raise EncryptionError("Invalid encrypted attribute envelope") from error
    if len(payload) < (16 if deterministic else 28):
        raise EncryptionError("Invalid encrypted attribute envelope")
    aad = _aad(context, deterministic)
    for key in reversed(_keys(deterministic)):
        try:
            plaintext = (
                _siv(key).decrypt(payload, [aad])
                if deterministic
                else AESGCM(key).decrypt(payload[:12], payload[12:], aad)
            )
            return plaintext.decode("utf-8")
        except (InvalidTag, UnicodeDecodeError):
            continue
    raise EncryptionError("Unable to decrypt attribute with the configured keys")
