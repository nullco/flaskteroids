import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app

from flaskteroids.exceptions import EncryptionError

_PREFIX = "flaskteroids:rich-text:v1:"


def generate_encryption_key():
    """Generate a dedicated, base64-encoded AES-256 key for encrypted credentials."""
    return base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode()


def is_encrypted(source):
    return isinstance(source, str) and source.startswith(_PREFIX)


def _keys():
    values = current_app.config.rich_text.encryption_keys
    if not values:
        value = os.environ.get("FLASKTEROIDS_RICH_TEXT_ENCRYPTION_KEY")
        if not value:
            value = (
                current_app.credentials.to_dict()
                .get("rich_text", {})
                .get("encryption_key")
            )
        values = [value] if value else []
    if not isinstance(values, (list, tuple)) or not values:
        raise EncryptionError(
            "Encrypted rich text requires a dedicated, base64-encoded 32-byte key "
            "in rich_text.encryption_key credentials, "
            "FLASKTEROIDS_RICH_TEXT_ENCRYPTION_KEY, or config.rich_text.encryption_keys."
        )
    keys = []
    for value in values:
        try:
            key = base64.b64decode(value, altchars=b"-_", validate=True)
        except (ValueError, TypeError) as error:
            raise EncryptionError("Invalid rich-text encryption key") from error
        if len(key) != 32:
            raise EncryptionError("Rich-text encryption keys must contain 32 bytes")
        keys.append(key)
    return keys


def encrypt(source):
    nonce = os.urandom(12)
    payload = AESGCM(_keys()[0]).encrypt(nonce, source.encode(), _PREFIX.encode())
    return _PREFIX + base64.urlsafe_b64encode(nonce + payload).decode()


def decrypt(source):
    if not is_encrypted(source):
        raise EncryptionError(
            "Encrypted rich text contains plaintext or an unsupported envelope. "
            "Run the rich-text record's encrypt() method to migrate plaintext "
            "before serving reads."
        )
    try:
        payload = base64.b64decode(
            source[len(_PREFIX) :], altchars=b"-_", validate=True
        )
    except (ValueError, TypeError) as error:
        raise EncryptionError("Invalid encrypted rich-text body") from error
    if len(payload) < 28:
        raise EncryptionError("Invalid encrypted rich-text body")
    for key in _keys():
        try:
            return (
                AESGCM(key)
                .decrypt(payload[:12], payload[12:], _PREFIX.encode())
                .decode()
            )
        except (InvalidTag, UnicodeDecodeError):
            continue
    raise EncryptionError("Unable to decrypt rich text with the configured keys")
