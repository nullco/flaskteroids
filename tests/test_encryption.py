import pytest

from flaskteroids.encryption import decrypt, encrypt, generate_encryption_key


@pytest.mark.parametrize("deterministic", [False, True])
def test_application_encryption_roundtrips_strings_without_models(
    app, app_ctx, deterministic
):
    app.config.encryption.primary_key = generate_encryption_key()
    app.config.encryption.deterministic_key = generate_encryption_key()

    ciphertext = encrypt(
        "Sensitive value",
        context="external_service.token",
        deterministic=deterministic,
    )

    assert ciphertext != "Sensitive value"
    assert (
        decrypt(
            ciphertext,
            context="external_service.token",
            deterministic=deterministic,
        )
        == "Sensitive value"
    )
