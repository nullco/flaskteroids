import pytest
from flaskteroids.credentials import (
    Credentials,
    CredentialsError,
    decrypt,
    encrypt,
    generate_key,
)


def test_encrypts_and_decrypts_credentials():
    key = generate_key()

    encrypted = encrypt("api_key: secret\n", key)

    assert encrypted != "api_key: secret\n"
    assert decrypt(encrypted, key) == "api_key: secret\n"


def test_loads_shared_credentials(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    key = generate_key()
    (config / "master.key").write_text(key)
    (config / "credentials.yml.enc").write_text(
        encrypt("payments:\n  api_key: secret\n", key)
    )

    credentials = Credentials(tmp_path, "development")

    assert credentials.payments.api_key == "secret"
    assert credentials["payments"]["api_key"] == "secret"


def test_environment_credentials_take_precedence(tmp_path):
    config = tmp_path / "config"
    credentials_path = config / "credentials"
    credentials_path.mkdir(parents=True)
    shared_key = generate_key()
    production_key = generate_key()
    (config / "master.key").write_text(shared_key)
    (config / "credentials.yml.enc").write_text(encrypt("name: shared\n", shared_key))
    (credentials_path / "production.key").write_text(production_key)
    (credentials_path / "production.yml.enc").write_text(
        encrypt("name: production\n", production_key)
    )

    credentials = Credentials(tmp_path, "production")

    assert credentials.name == "production"


def test_master_key_environment_variable_takes_precedence(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    file_key = generate_key()
    environment_key = generate_key()
    (config / "master.key").write_text(file_key)
    (config / "credentials.yml.enc").write_text(
        encrypt("name: environment\n", environment_key)
    )

    credentials = Credentials(
        tmp_path,
        "development",
        environ={"FLASKTEROIDS_MASTER_KEY": environment_key},
    )

    assert credentials.name == "environment"


def test_missing_key_raises_for_encrypted_credentials(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "credentials.yml.enc").write_text("encrypted")

    with pytest.raises(CredentialsError, match="Missing encryption key"):
        Credentials(tmp_path, "development").to_dict()
