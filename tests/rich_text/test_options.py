import base64
import os

import pytest
from sqlalchemy import select, update

from flaskteroids.db import session
from flaskteroids.exceptions import EncryptionError, StrictLoadingViolationError
from flaskteroids.rich_text import generate_encryption_key
from tests.rich_text.app.models.default_note import DefaultNote
from tests.rich_text.app.models.entry import Entry

pytestmark = pytest.mark.usefixtures("app_ctx")


@pytest.fixture
def encryption_keys(app):
    keys = [base64.urlsafe_b64encode(os.urandom(32)).decode() for _ in range(2)]
    app.config.rich_text.encryption_keys = keys[:1]
    return keys


def stored_body(owner, name="content"):
    table = Entry.metadata.tables["rich_texts"]
    return session.scalar(
        select(table.c.body).where(
            table.c.record_type == "Entry",
            table.c.record_id == owner.id,
            table.c.name == name,
        )
    )


def test_encryption_keeps_plaintext_out_of_storage_and_roundtrips_body(encryption_keys):
    owner = Entry.create(title="Private", content="<strong>Secret</strong>")
    assert "Secret" not in stored_body(owner)
    assert owner.reload().content.to_plain_text() == "Secret"
    assert owner.content.update(body="<em>Revised secret</em>")
    assert owner.content.reload().to_plain_text() == "Revised secret"
    assert "Revised" not in stored_body(owner)


def test_explicit_encrypt_migrates_existing_plaintext(encryption_keys):
    owner = Entry.create(content="Before migration")
    table = Entry.metadata.tables["rich_texts"]
    session.execute(
        update(table)
        .where(table.c.id == owner.content.id)
        .values(body="<strong>Migrate</strong>")
    )
    session.commit()
    rich = owner.content.reload()
    assert rich.encrypt()
    assert "Migrate" not in stored_body(owner)
    assert rich.reload().to_plain_text() == "Migrate"


def test_environment_key_configures_encryption_without_application_plumbing(
    monkeypatch,
):
    monkeypatch.setenv(
        "FLASKTEROIDS_RICH_TEXT_ENCRYPTION_KEY", generate_encryption_key()
    )
    owner = Entry.create(content="Environment secret")
    assert owner.reload().content.to_plain_text() == "Environment secret"


def test_explicit_encrypt_preserves_a_new_owners_assigned_body(encryption_keys):
    owner = Entry.new(content="Assigned draft")
    assert owner.content.encrypt()
    assert owner.reload().content.to_plain_text() == "Assigned draft"


def test_explicit_encrypt_rejects_unknown_envelopes(encryption_keys):
    owner = Entry.create(content="Secret")
    table = Entry.metadata.tables["rich_texts"]
    session.execute(
        update(table)
        .where(table.c.id == owner.content.id)
        .values(body="flaskteroids:rich-text:v999:unknown")
    )
    session.commit()
    with pytest.raises(EncryptionError):
        owner.content.reload().encrypt()


def test_encryption_is_nondeterministic(encryption_keys):
    first = Entry.create(content="Same")
    second = Entry.create(content="Same")
    assert stored_body(first) != stored_body(second)


def test_encryption_rotation_reads_old_keys_and_writes_with_the_current_key(
    app, encryption_keys
):
    owner = Entry.create(content="Secret")
    original = stored_body(owner)
    app.config.rich_text.encryption_keys = [encryption_keys[1], encryption_keys[0]]
    assert owner.reload().content.to_plain_text() == "Secret"
    assert owner.content.encrypt()
    assert stored_body(owner) != original
    app.config.rich_text.encryption_keys = [encryption_keys[1]]
    assert owner.content.reload().to_plain_text() == "Secret"


def test_encryption_fails_closed_without_a_key(monkeypatch):
    monkeypatch.delenv("FLASKTEROIDS_RICH_TEXT_ENCRYPTION_KEY", raising=False)
    with pytest.raises(EncryptionError):
        Entry.create(content="Never store plaintext")
    assert Entry.count() == 0


def test_encryption_rejects_wrong_keys_and_plaintext_rows(app, encryption_keys):
    owner = Entry.create(content="Secret")
    app.config.rich_text.encryption_keys = [encryption_keys[1]]
    with pytest.raises(EncryptionError):
        owner.reload().content.to_plain_text()
    table = Entry.metadata.tables["rich_texts"]
    session.execute(
        update(table).where(table.c.id == owner.content.id).values(body="Plaintext")
    )
    session.commit()
    with pytest.raises(EncryptionError):
        owner.content.reload().to_plain_text()


def test_encryption_rejects_modified_ciphertext(encryption_keys):
    owner = Entry.create(content="Secret")
    table = Entry.metadata.tables["rich_texts"]
    original = stored_body(owner)
    prefix, payload = original.rsplit(":", 1)
    decoded = bytearray(base64.urlsafe_b64decode(payload))
    decoded[-1] ^= 1
    tampered = prefix + ":" + base64.urlsafe_b64encode(decoded).decode()
    session.execute(
        update(table).where(table.c.id == owner.content.id).values(body=tampered)
    )
    session.commit()
    with pytest.raises(EncryptionError):
        owner.reload().content.to_plain_text()


def test_strict_loading_rejects_lazy_reads_and_supports_eager_scopes():
    owner = Entry.create(restricted="Restricted")
    identity = owner.id
    session.expunge_all()
    unloaded = Entry.find(identity)
    with pytest.raises(StrictLoadingViolationError):
        _ = unloaded.restricted
    with pytest.raises(StrictLoadingViolationError):
        _ = unloaded.rich_text_restricted
    loaded = Entry.with_rich_text_restricted().find(identity)
    assert loaded.restricted.to_plain_text() == "Restricted"


def test_strict_loading_inherits_application_defaults_and_allows_field_overrides():
    owner = DefaultNote.create(content="Strict", relaxed="Lazy permitted")
    identity = owner.id
    session.expunge_all()
    owner = DefaultNote.find(identity)
    assert owner.relaxed.to_plain_text() == "Lazy permitted"
    with pytest.raises(StrictLoadingViolationError):
        _ = owner.content


def test_forms_load_only_the_requested_rich_text_field(app):
    from flask import render_template_string

    owner = Entry.create(restricted="Strict", summary="Optional")
    identity = owner.id
    session.expunge_all()
    with app.test_request_context():
        rendered = render_template_string(
            '{% call(form) form_with(model=record, url="/entries") %}'
            '{{ form.rich_text_area("summary") }}{% endcall %}',
            record=Entry.find(identity),
        )
    assert "Optional" in rendered


def test_strict_loading_permits_assignment_on_new_owners():
    owner = Entry.new(restricted="New")
    assert owner.save()
    assert owner.restricted.to_plain_text() == "New"


@pytest.mark.parametrize("value", [None, "", "<div><br></div>"])
def test_store_if_blank_skips_new_rows_and_removes_existing_rows(value):
    owner = Entry.create(summary=value)
    assert stored_body(owner, "summary") is None
    assert owner.update(summary="Present")
    assert stored_body(owner, "summary") == "Present"
    assert owner.update(summary=value)
    assert stored_body(owner, "summary") is None


def test_blank_removal_waits_for_successful_owner_validation():
    owner = Entry.create(title="Valid", summary="Original")
    assert not owner.update(summary="", title="")
    assert owner.summary.blank()
    assert owner.reload().summary.to_plain_text() == "Original"
