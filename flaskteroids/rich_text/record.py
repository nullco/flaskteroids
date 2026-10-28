from datetime import UTC, datetime

from flask import current_app
from sqlalchemy import event, inspect, update
from sqlalchemy.orm import attributes

from flaskteroids import encryption
from flaskteroids._models.errors import Errors
from flaskteroids.attachments import attached as attached_storage
from flaskteroids.attachments.attached import has_many_attached
from flaskteroids.db import session, transactional
from flaskteroids.declarations import model_for
from flaskteroids.exceptions import (
    EncryptionError,
    ProgrammerError,
    RecordNotFoundException,
)
from flaskteroids.rich_text.content import Content
from flaskteroids.rich_text.embeds import preload_rows


class RichText:
    """A persisted rich-text record whose body autosaves with its owner."""

    has_many_attached("embeds")

    def __init__(self):
        self._initialize()

    def _initialize(self):
        self._changes = {}
        self._attachment_changes = {}
        self._attachment_cache = {}
        self._errors = Errors()
        self._record = None
        self._marked_for_destruction = False

    @property
    def record(self):
        if self._record is None:
            model = current_app.extensions["flaskteroids.db"].models.get(
                self.record_type
            )
            if model is None:
                raise ProgrammerError(f"Unknown rich-text owner {self.record_type}")
            self._record = model.find(self.record_id)
        return self._record

    @property
    def _definition(self):
        return model_for(type(self.record)).rich_texts[self.name]

    @property
    def body(self):
        if "body" in self._changes:
            return self._changes["body"]
        source = self._body or ""
        if self._definition.encrypted and self._body is not None:
            source = encryption.decrypt(
                source, context=f"{self.record_type}.{self.name}"
            )
        elif encryption.is_encrypted(source):
            raise EncryptionError("Encrypted rich-text bodies require encrypted=True")
        return Content(source, _record=self)

    @body.setter
    def body(self, value):
        if isinstance(value, RichText):
            value = value.body
        if value is None:
            value = Content()
        elif isinstance(value, str):
            value = Content(value)
        elif not isinstance(value, Content):
            raise TypeError("Rich-text body expects an HTML string, Content, or None")
        self._changes["body"] = Content(value._source, _record=self)
        self._marked_for_destruction = False
        self.record._rich_text_changes[self.name] = self

    @property
    def errors(self):
        return self._errors

    def is_new_record(self):
        state = inspect(self)
        return state.transient or state.pending

    def is_persisted(self):
        state = inspect(self)
        return (state.persistent or state.detached) and not state.was_deleted

    def is_valid(self):
        self._errors = Errors()
        self._attachment_changes["embeds"] = self.body.attachables
        attached_storage.validate(self)
        return not self.errors

    @classmethod
    def find(cls, id):
        models = current_app.extensions["flaskteroids.db"].models.values()
        model = next((model for model in models if model_for(model).rich_texts), None)
        if model is None:
            raise RecordNotFoundException(f"Rich text {id} was not found")
        model.prepare()
        row_type = (
            inspect(model)
            .relationships[f"rich_text_{next(iter(model_for(model).rich_texts))}"]
            .mapper.class_
        )
        row = session.get(row_type, id)
        if row is None:
            raise RecordNotFoundException(f"Rich text {id} was not found")
        return row

    def _require_owner(self):
        owner = self.record
        current_app.extensions["flaskteroids.db"].require_model(type(owner))
        if inspect(type(self)).registry is not owner.registry:
            raise ProgrammerError("Rich text belongs to another application registry")
        return owner

    @transactional(rollback_on_false=True)
    def save(self, validate=True):
        owner = self._require_owner()
        if inspect(self).was_deleted or inspect(owner).was_deleted:
            raise ProgrammerError("A destroyed rich-text record cannot be saved")
        if owner.is_new_record():
            owner._rich_text_changes[self.name] = self
            saved = owner.save(validate=validate)
            if not saved and not self.errors:
                self.errors.append(("record", "Rich-text owner is invalid"))
            return saved
        if validate and not self.is_valid():
            return False
        self._publish()
        session.add(self)
        session.flush()
        self._persist_embeds()
        self._touch_owner()
        self._changes.clear()
        owner._rich_text_changes.pop(self.name, None)
        return True

    def encrypt(self):
        """Encrypt an existing plaintext body or rotate it to the current key."""
        if not self._definition.encrypted:
            raise EncryptionError("Declare encrypted=True before encrypting rich text")
        if "body" in self._changes or encryption.is_encrypted(self._body):
            source = self.body._source
        elif self._body and self._body.startswith("flaskteroids:encrypted:"):
            raise EncryptionError("Unsupported attribute encryption envelope")
        else:
            source = self._body or ""
        self.body = source
        return self.save()

    def update(self, *, body):
        self.body = body
        return self.save()

    def reload(self):
        self._require_owner()
        session.refresh(self)
        self._changes.clear()
        self._attachment_changes.clear()
        self._attachment_cache.clear()
        self.record._rich_text_changes.pop(self.name, None)
        return self

    @transactional
    def destroy(self):
        self._require_owner()
        if self.is_new_record():
            return False
        attached_storage.destroy(self)
        session.delete(self)
        session.flush()
        owner = self.record
        attributes.set_committed_value(owner, f"rich_text_{self.name}", None)
        owner._rich_text_changes.pop(self.name, None)
        self._touch_owner()
        return True

    def _publish(self):
        now = datetime.now(UTC)
        if self.is_new_record():
            self.record_id = self.record.id
            self.created_at = now
        if "body" in self._changes or self.is_new_record():
            source = self.body.to_html()
            self._body = (
                encryption.encrypt(source, context=f"{self.record_type}.{self.name}")
                if self._definition.encrypted
                else source
            )
        self.updated_at = now
        setattr(self.record, f"rich_text_{self.name}", self)

    def _persist_embeds(self):
        self._attachment_changes["embeds"] = self.body.attachables
        attached_storage.persist(self)
        preload_rows([self])

    def _touch_owner(self):
        owner = self.record
        if "updated_at" in owner.column_names:
            now = datetime.now(UTC)
            table = owner.__table__
            session.execute(
                update(table).where(table.c.id == owner.id).values(updated_at=now)
            )
            attributes.set_committed_value(owner, "updated_at", now)

    def to_plain_text(self):
        return self.body.to_plain_text()

    def to_editor_html(self):
        return self.body.to_editor_html()

    def blank(self):
        return self.body.blank()

    def present(self):
        return not self.blank()

    def __bool__(self):
        return self.present()

    def __str__(self):
        return str(self.body)

    def __html__(self):
        return self.body.__html__()

    def __repr__(self):
        return f"<RichText id={self.id!r} name={self.name!r}>"

    def __json__(self):
        return {"id": self.id, "name": self.name, "body": self.body.to_html()}


@event.listens_for(RichText, "load", propagate=True)
def _loaded(record, context):
    record._initialize()


@event.listens_for(RichText, "expire", propagate=True)
def _expired(record, attrs):
    if record is not None:
        record._attachment_cache.clear()
