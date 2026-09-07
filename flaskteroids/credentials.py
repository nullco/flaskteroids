import base64
import os
import secrets
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import yaml


class CredentialsError(RuntimeError):
    pass


class Credentials:
    def __init__(
        self, root, environment, *, environ=None, environment_specific=False
    ):
        self.root = Path(root)
        self.environment = str(environment)
        self.environ = os.environ if environ is None else environ
        self.environment_specific = environment_specific
        self._data = None

    def __getattr__(self, name):
        value = self._load().get(name)
        return _wrap(value)

    def __getitem__(self, name):
        return _wrap(self._load()[name])

    def get(self, name, default=None):
        return _wrap(self._load().get(name, default))

    def to_dict(self):
        return self._load().copy()

    @property
    def content_path(self):
        environment_path = (
            self.root / "config" / "credentials" / f"{self.environment}.yml.enc"
        )
        if self.environment_specific or environment_path.exists():
            return environment_path
        return self.root / "config" / "credentials.yml.enc"

    @property
    def key_path(self):
        if self.content_path.parent.name == "credentials":
            return self.root / "config" / "credentials" / f"{self.environment}.key"
        return self.root / "config" / "master.key"

    def key(self):
        value = self.environ.get("FLASKTEROIDS_MASTER_KEY")
        if value:
            return value.strip()
        if self.key_path.exists():
            return self.key_path.read_text().strip()
        return None

    def reload(self):
        self._data = None
        return self

    def _load(self):
        if self._data is not None:
            return self._data
        if not self.content_path.exists():
            self._data = {}
            return self._data
        key = self.key()
        if not key:
            raise CredentialsError(
                f"Missing encryption key to decrypt {self.content_path}. "
                "Set FLASKTEROIDS_MASTER_KEY or provide the key file."
            )
        plaintext = decrypt(self.content_path.read_text(), key)
        data = yaml.safe_load(plaintext) or {}
        if not isinstance(data, dict):
            raise CredentialsError("Credentials must contain a YAML mapping")
        self._data = data
        return self._data


class CredentialOptions:
    def __init__(self, values):
        self._values = values

    def __getattr__(self, name):
        return _wrap(self._values.get(name))

    def __getitem__(self, name):
        return _wrap(self._values[name])

    def get(self, name, default=None):
        return _wrap(self._values.get(name, default))


def generate_key():
    return secrets.token_hex(32)


def encrypt(plaintext, key):
    key_bytes = _key_bytes(key)
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(key_bytes).encrypt(nonce, plaintext.encode(), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt(payload, key):
    try:
        encrypted = base64.urlsafe_b64decode(payload.strip().encode())
        nonce, ciphertext = encrypted[:12], encrypted[12:]
        return AESGCM(_key_bytes(key)).decrypt(nonce, ciphertext, None).decode()
    except Exception as error:
        raise CredentialsError("Unable to decrypt credentials") from error


def _key_bytes(key):
    try:
        value = bytes.fromhex(key.strip())
    except ValueError as error:
        raise CredentialsError(
            "The credentials key must be a 64-character hexadecimal value"
        ) from error
    if len(value) != 32:
        raise CredentialsError(
            "The credentials key must be a 64-character hexadecimal value"
        )
    return value


def _wrap(value):
    if isinstance(value, dict):
        return CredentialOptions(value)
    return value
