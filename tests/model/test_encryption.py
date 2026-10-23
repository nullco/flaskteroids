import base64
from types import SimpleNamespace

import pytest
from flask import current_app
from sqlalchemy import Column, Enum, Integer, String, Table, Text, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base

from flaskteroids.configuration import Options
from flaskteroids.db import session
from flaskteroids.encryption import generate_encryption_key
from flaskteroids.exceptions import EncryptionError, ProgrammerError
from flaskteroids.form import Form
from flaskteroids.model import encrypts, validates
from tests.model.schema_support import model_base

Base = declarative_base()


class AccountTable(Base):
    __tablename__ = "encrypted_accounts"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(Text, unique=True)
    notes = Column(Text)
    other_notes = Column(Text)


class ShortSecretTable(Base):
    __tablename__ = "short_secrets"

    id = Column(Integer, primary_key=True)
    value = Column(String(20))


class ApplicationModel(model_base(Base)):
    __abstract__ = True

    encrypts("notes")


class Account(ApplicationModel):
    __table_name__ = "encrypted_accounts"

    encrypts("email", deterministic=True, downcase=True)
    encrypts("other_notes")
    validates("name", presence=True)
    validates("notes", length={"maximum": 50})


class ShortSecret(model_base(Base)):
    encrypts("value")


@pytest.fixture
def encrypted(init_models):
    init_models(Base, [(AccountTable, Account), (ShortSecretTable, ShortSecret)])
    keys = [generate_encryption_key() for _ in range(3)]
    current_app.config.encryption = Options(
        {
            "primary_key": keys[0],
            "deterministic_key": keys[1],
            "support_unencrypted_data": False,
        }
    )
    return SimpleNamespace(
        Account=Account,
        session=session,
        keys=keys,
        config=current_app.config.encryption,
    )


@pytest.mark.parametrize(
    "key_name,attribute",
    [("primary_key", "notes"), ("deterministic_key", "email")],
)
@pytest.mark.parametrize("source", ["configuration", "environment", "credentials"])
def test_encryption_keys_follow_configuration_environment_credentials_precedence(
    encrypted, monkeypatch, mocker, key_name, attribute, source
):
    configured_key, environment_key, credentials_key = encrypted.keys
    variable = f"FLASKTEROIDS_ENCRYPTION_{key_name.upper()}"
    monkeypatch.delenv(variable, raising=False)
    credentials = mocker.Mock()
    credentials.to_dict.return_value = {"encryption": {key_name: credentials_key}}
    monkeypatch.setattr(current_app, "credentials", credentials, raising=False)
    setattr(
        encrypted.config,
        key_name,
        configured_key if source == "configuration" else None,
    )
    if source != "credentials":
        monkeypatch.setenv(variable, environment_key)

    account = Account.create(name="Ada", **{attribute: "secret@example.com"})

    expected_key = {
        "configuration": configured_key,
        "environment": environment_key,
        "credentials": credentials_key,
    }[source]
    setattr(encrypted.config, key_name, expected_key)
    assert getattr(account.reload(), attribute) == "secret@example.com"


@pytest.mark.parametrize("value", [None, "", "Private notes", "Español 日本語 🔐"])
def test_encrypted_attributes_roundtrip_through_storage(encrypted, value):
    account = Account.create(name="Ada", notes=value)
    ciphertext = account.ciphertext_for("notes")
    with encrypted.session.connection().execute(
        text("SELECT notes FROM encrypted_accounts WHERE id = :id"), {"id": account.id}
    ) as result:
        assert result.scalar_one() == ciphertext
    if value is not None:
        assert ciphertext != value
        assert ciphertext.startswith("flaskteroids:encrypted:v1:gcm:")
    assert account.reload().notes == value
    assert account.__json__()["notes"] == value


def test_randomized_encryption_produces_distinct_ciphertexts(encrypted):
    first = Account.create(name="Ada", notes="Same")
    second = Account.create(name="Grace", notes="Same")
    assert first.ciphertext_for("notes") != second.ciphertext_for("notes")


def test_deterministic_encryption_normalizes_assignment_and_queries(encrypted):
    account = Account.create(name="Ada", email="Ada@EXAMPLE.COM")
    assert account.email == "ada@example.com"
    assert account.reload().email == "ada@example.com"
    assert Account.find_by(email="ADA@example.com") is account
    assert (
        Account.where(Account.email.in_(["unknown", "ADA@EXAMPLE.COM"])).first()
        is account
    )
    assert (
        encrypted.session.scalar(
            select(Account).where(Account.email == "ADA@example.com")
        )
        is account
    )
    assert "ADA@example.com" not in Account.where(email="ADA@example.com").to_sql()


def test_deterministic_encryption_supports_database_uniqueness(encrypted):
    Account.create(name="Ada", email="ada@example.com")
    with pytest.raises(IntegrityError):
        Account.create(name="Duplicate", email="ADA@EXAMPLE.COM")
    assert Account.count() == 1


@pytest.mark.parametrize("deterministic", [False, True])
def test_encrypted_attributes_support_null_queries(encrypted, deterministic):
    account = Account.create(name="Ada")
    field = "email" if deterministic else "notes"
    assert Account.where(**{field: None}).first() is account


@pytest.mark.parametrize(
    "query",
    [
        lambda: Account.where(notes="Private"),
        lambda: Account.where(Account.notes.in_(["Private"])),
        lambda: Account.where(Account.email.like("%@example.com")),
        lambda: Account.where(Account.email > "a"),
        lambda: Account.order(email="asc"),
        lambda: Account.order(Account.email),
        lambda: Account.order("email"),
    ],
)
def test_encrypted_queries_reject_unsupported_operations(encrypted, query):
    with pytest.raises(EncryptionError):
        query()


def test_validation_failure_retains_plaintext_for_form_redisplay(encrypted):
    account = Account.create(name="Ada", notes="Original")
    assert not account.update(name="", notes="Retained input")
    assert account.notes == "Retained input"
    with current_app.test_request_context():
        form = Form("account", {"notes": account.notes}, model=account)
        assert "Retained input" in str(form.text_area("notes"))
    assert Account.find(account.id).reload().notes == "Original"


def test_encrypted_changes_track_plaintext_and_reload_discards_assignment(encrypted):
    account = Account.create(name="Ada", notes="Original")
    assert account.update(notes="Revised")
    assert account.saved_change_to_attribute("notes") == ("Original", "Revised")
    account.notes = "Unpublished"
    assert account.changes["notes"] == "Unpublished"
    assert account.reload().notes == "Revised"


def test_model_inspection_filters_encrypted_attributes(encrypted):
    account = Account.create(name="Ada", notes="Secret", email="ada@example.com")
    assert "Ada" in repr(account)
    assert "Secret" not in repr(account)
    assert "ada@example.com" not in repr(account)
    assert "notes" not in repr(account)


def test_rotation_reads_previous_keys_and_encrypt_preserves_other_pending_input(
    encrypted,
):
    account = Account.create(name="Ada", email="ada@example.com", notes="Secret")
    original = account.ciphertext_for("notes")
    encrypted.config.primary_key = [encrypted.keys[0], encrypted.keys[2]]
    assert account.reload().notes == "Secret"
    account.name = "Unsaved name"
    assert account.encrypt()
    assert account.name == "Unsaved name"
    assert account.changes == {"name": "Unsaved name"}
    assert account.ciphertext_for("notes") != original
    encrypted.config.primary_key = encrypted.keys[2]
    assert account.reload().notes == "Secret"
    assert account.name == "Ada"
    assert Account.find_by(email="ada@example.com") is account


def test_reencryption_participates_in_the_model_transaction(encrypted):
    account = Account.create(name="Ada", notes="Secret")
    original = account.ciphertext_for("notes")
    with pytest.raises(RuntimeError, match="abort"):
        with Account.transaction():
            account.encrypt()
            raise RuntimeError("abort")
    assert account.ciphertext_for("notes") == original
    assert account.reload().notes == "Secret"


def test_plaintext_migration_requires_explicit_configuration(encrypted):
    account = Account.create(name="Ada", notes="Original")
    encrypted.session.execute(
        text("UPDATE encrypted_accounts SET notes = :value WHERE id = :id"),
        {"value": "Import", "id": account.id},
    )
    encrypted.session.commit()
    with pytest.raises(EncryptionError):
        account.reload()
    encrypted.config.support_unencrypted_data = True
    assert account.reload().notes == "Import"
    assert account.encrypt()
    encrypted.config.support_unencrypted_data = False
    assert account.reload().notes == "Import"
    assert account.ciphertext_for("notes") != "Import"


@pytest.mark.parametrize(
    "replacement", ["corrupt", "flaskteroids:encrypted:v999:unknown"]
)
def test_encrypted_attributes_reject_corrupt_storage(encrypted, replacement):
    account = Account.create(name="Ada", notes="Secret")
    encrypted.session.execute(
        text("UPDATE encrypted_accounts SET notes = :value WHERE id = :id"),
        {"value": replacement, "id": account.id},
    )
    encrypted.session.commit()
    with pytest.raises(EncryptionError):
        account.reload()


@pytest.mark.parametrize("configured", [False, "false", "true", 1])
def test_plaintext_reads_require_an_explicit_boolean_opt_in(encrypted, configured):
    account = Account.create(name="Ada", notes="Secret")
    encrypted.session.execute(
        text("UPDATE encrypted_accounts SET notes = :value WHERE id = :id"),
        {"value": "Plaintext", "id": account.id},
    )
    encrypted.session.commit()
    encrypted.config.support_unencrypted_data = configured
    with pytest.raises(EncryptionError):
        account.reload()


def test_authenticated_encryption_rejects_ciphertext_moved_between_attributes(
    encrypted,
):
    account = Account.create(name="Ada", notes="Secret")
    encrypted.session.execute(
        text("UPDATE encrypted_accounts SET other_notes = notes WHERE id = :id"),
        {"id": account.id},
    )
    encrypted.session.commit()
    with pytest.raises(EncryptionError):
        account.reload()


@pytest.mark.parametrize("key", [None, "", "invalid", 123, [None]])
def test_invalid_keys_reject_persistence_without_exposing_plaintext(
    encrypted, monkeypatch, key
):
    monkeypatch.delenv("FLASKTEROIDS_ENCRYPTION_PRIMARY_KEY", raising=False)
    encrypted.config.primary_key = key
    with pytest.raises(EncryptionError) as failure:
        Account.create(name="Ada", notes="Secret")
    assert "Secret" not in str(failure.value)
    assert Account.count() == 0


def test_wrong_keys_reject_reads(encrypted):
    account = Account.create(name="Ada", notes="Secret")
    encrypted.config.primary_key = encrypted.keys[2]
    with pytest.raises(EncryptionError):
        account.reload()


def test_native_mapped_writes_encrypt_attributes(encrypted):
    account = Account.create(name="Ada", notes="Original")
    encrypted.session.execute(
        update(Account).where(Account.id == account.id).values(notes="Native update")
    )
    encrypted.session.commit()
    assert account.reload().notes == "Native update"
    assert "Native update" not in account.ciphertext_for("notes")


def test_deterministic_encryption_rejects_tampered_ciphertext(encrypted):
    account = Account.create(name="Ada", email="ada@example.com")
    prefix, encoded = account.ciphertext_for("email").rsplit(":", 1)
    payload = bytearray(base64.urlsafe_b64decode(encoded))
    payload[-1] ^= 1
    encrypted.session.execute(
        text("UPDATE encrypted_accounts SET email = :value WHERE id = :id"),
        {
            "value": prefix + ":" + base64.urlsafe_b64encode(payload).decode(),
            "id": account.id,
        },
    )
    encrypted.session.commit()
    with pytest.raises(EncryptionError):
        account.reload()


def test_deterministic_encryption_requires_a_separate_key(encrypted, monkeypatch):
    monkeypatch.delenv("FLASKTEROIDS_ENCRYPTION_DETERMINISTIC_KEY", raising=False)
    encrypted.config.deterministic_key = None
    with pytest.raises(EncryptionError):
        Account.create(name="Ada", email="ada@example.com")
    assert Account.count() == 0


def test_ordering_plaintext_attributes_preserves_query_semantics(encrypted):
    Account.create(name="Grace")
    first = Account.create(name="Ada")
    assert Account.order("name").first() is first


def test_ciphertext_size_errors_recommend_suitable_storage(encrypted):
    with pytest.raises(EncryptionError, match="column size"):
        ShortSecret.create(value="Secret")
    assert ShortSecret.count() == 0


def test_encrypted_declarations_are_inherited_and_listed(encrypted):
    assert Account.encrypted_attributes() == {"email", "notes", "other_notes"}
    assert ShortSecret.encrypted_attributes() == {"value"}


@pytest.mark.parametrize(
    "column,options",
    [
        (Column("secret", Integer), {}),
        (Column("secret", Enum("public", "private")), {}),
        (Column("secret", Text, primary_key=True), {}),
        (Column("secret", Text, server_default="Plaintext"), {}),
        (Column("secret", Text, unique=True), {}),
        (Column("other", Text), {}),
    ],
)
def test_encryption_declarations_reject_unsuitable_columns(column, options):
    base = declarative_base()
    Table(
        "invalid_records",
        base.metadata,
        Column("id", Integer, primary_key=True),
        column,
    )

    class InvalidRecord(model_base(base)):
        encrypts("secret", **options)

    with pytest.raises(ProgrammerError):
        InvalidRecord.prepare()
