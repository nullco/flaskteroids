from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from flask import current_app
from sqlalchemy import insert, select
from werkzeug.datastructures import FileStorage

from flaskteroids.attachments.blob import Attachment, Blob, Upload, storage
from flaskteroids.attachments.operations import purge_blob_after_commit, upload_blob
from flaskteroids.attachments.schema import attachments
from flaskteroids.attachments.transactions import after_commit, defer_uploads
from flaskteroids.callbacks import _COMMIT_CALLBACKS
from flaskteroids.db import session, transactional
from flaskteroids.declarations import model_for
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.rules import declaration
from flaskteroids.storage import StorageError


@dataclass(frozen=True)
class Definition:
    name: str
    many: bool
    service: str | Callable | None
    dependent: str | None
    max_size: int | None
    content_types: tuple


@declaration
def has_one_attached(
    name, *, service=None, dependent="purge_later", max_size=None, content_types=()
):
    return _declare(name, False, service, dependent, max_size, content_types)


@declaration
def has_many_attached(
    name, *, service=None, dependent="purge_later", max_size=None, content_types=()
):
    return _declare(name, True, service, dependent, max_size, content_types)


def _declare(name, many, service, dependent, max_size, content_types):
    if not name.isidentifier() or name.startswith("_"):
        raise ProgrammerError("Attachment names must be public Python identifiers")
    if dependent not in {None, "purge", "purge_later"}:
        raise ProgrammerError(
            "Attachment dependent must be purge, purge_later, or None"
        )
    if max_size is not None and (type(max_size) is not int or max_size < 1):
        raise ProgrammerError("Attachment max_size must be a positive integer")
    if isinstance(content_types, str):
        content_types = (content_types,)
    definition = Definition(
        name, many, service, dependent, max_size, tuple(content_types)
    )

    def bind(cls):
        inherited = any(
            name in model_for(base).attachments
            for base in cls.__mro__[1:]
            if base is not object
        )
        if name in dir(cls) and not inherited:
            raise ProgrammerError(f"Attachment {name} conflicts with a model attribute")
        model_for(cls).attachments[name] = definition
        wrapper = AttachedMany if many else AttachedOne
        setattr(cls, name, property(lambda instance: wrapper(instance, definition)))

    return bind


def assign(instance, name, attachable):
    definition = model_for(instance.__class__).attachments.get(name)
    if definition is None:
        return False
    if isinstance(attachable, FileStorage) and not attachable.filename:
        return True
    values = (
        attachable
        if definition.many and isinstance(attachable, (tuple, list))
        else [attachable]
    )
    maximum = current_app.config.attachments.max_upload_size
    pending = []
    for value in values:
        if value is None or isinstance(value, str) and value == "":
            continue
        if isinstance(value, FileStorage) and not value.filename:
            continue
        if isinstance(value, (Blob, Upload)):
            pending.append(value)
        elif isinstance(value, str):
            pending.append(Blob.find_signed_or_raise(value))
        elif isinstance(value, FileStorage):
            pending.append(
                Upload.read(
                    value.stream,
                    filename=value.filename,
                    max_size=maximum,
                    content_type=value.content_type,
                )
            )
        elif isinstance(value, dict) and "io" in value and "filename" in value:
            pending.append(
                Upload.read(
                    value["io"],
                    filename=value["filename"],
                    max_size=maximum,
                    content_type=value.get("content_type"),
                    identify=value.get("identify", True),
                )
            )
        elif isinstance(value, Path):
            with value.open("rb") as stream:
                pending.append(
                    Upload.read(stream, filename=value.name, max_size=maximum)
                )
        elif hasattr(value, "read") and isinstance(getattr(value, "name", None), str):
            pending.append(Upload.read(value, filename=value.name, max_size=maximum))
        else:
            raise StorageError(
                "Attach a file upload, Blob, signed blob ID, file, path, or io/filename mapping"
            )
    instance._attachment_changes[name] = pending
    return True


def validate(instance):
    definitions = model_for(instance.__class__).attachments
    for name, values in instance._attachment_changes.items():
        definition = definitions[name]
        for value in values:
            if definition.max_size and value.byte_size > definition.max_size:
                instance.errors.append(
                    (name, f"{name} exceeds {definition.max_size} bytes")
                )
            if (
                definition.content_types
                and value.content_type not in definition.content_types
            ):
                instance.errors.append(
                    (name, f"{name} has an unsupported content type")
                )


def persist(instance):
    definitions = model_for(instance.__class__).attachments
    removals = []
    for name, values in list(instance._attachment_changes.items()):
        definition = definitions[name]
        proxy = (AttachedMany if definition.many else AttachedOne)(instance, definition)
        existing = proxy.attachments
        service_name = (
            definition.service(instance)
            if callable(definition.service)
            else definition.service
        )
        new_blobs = [
            Blob._create(value, service_name or storage().service_name)
            if isinstance(value, Upload)
            else Blob.find(value.id)
            for value in values
        ]
        deferred = {
            blob.key: (
                lambda blob=blob, value=value: upload_blob(blob, value),
                value.close,
            )
            for blob, value in zip(new_blobs, values, strict=True)
            if isinstance(value, Upload)
        }
        defer_uploads(
            session,
            (instance.__class__.__name__, instance.id, name),
            deferred,
            append=definition.many and bool(new_blobs),
        )
        kept_ids = {blob.id for blob in new_blobs}
        existing_ids = {entry.blob_id for entry in existing}
        for entry in existing:
            if entry.blob_id not in kept_ids:
                removals.append((entry, definition.dependent))
        for blob in new_blobs:
            if blob.id in existing_ids:
                continue
            session.execute(
                insert(attachments).values(
                    name=name,
                    record_type=instance.__class__.__name__,
                    record_id=instance.id,
                    blob_id=blob.id,
                    created_at=datetime.now(UTC),
                )
            )
            existing_ids.add(blob.id)
        instance._attachment_changes.pop(name)
    for entry, dependent in removals:
        _remove(entry, dependent)
    cache_for_commit(instance)


def cache_for_commit(instance):
    if model_for(instance.__class__).callbacks.get("after_commit"):
        definitions = model_for(instance.__class__).attachments
        for definition in definitions.values():
            entries = AttachedMany(instance, definition).attachments
            instance._attachment_cache[definition.name] = [
                replace(entry, _blob=entry.blob) for entry in entries
            ]


def destroy(instance):
    for definition in model_for(instance.__class__).attachments.values():
        defer_uploads(
            session,
            (instance.__class__.__name__, instance.id, definition.name),
            {},
            append=False,
        )
        for entry in AttachedMany(instance, definition).attachments:
            _remove(entry, definition.dependent)
        instance._attachment_cache[definition.name] = []


def _remove(entry, dependent):
    if dependent == "purge_later":
        entry.purge_later()
    elif dependent == "purge":
        blob = entry.blob
        entry.detach()
        after_commit(
            session,
            lambda: purge_blob_after_commit(blob.id, blob.key, blob.service_name),
        )
    else:
        entry.detach()


class AttachedMany:
    def __init__(self, record, definition):
        self.record = record
        self.definition = definition

    @property
    def attachments(self):
        if self.record.is_new_record():
            return []
        if (
            not session.is_active or session.info.get(_COMMIT_CALLBACKS)
        ) and self.definition.name in self.record._attachment_cache:
            return self.record._attachment_cache[self.definition.name]
        query = (
            select(attachments)
            .where(
                attachments.c.record_type == self.record.__class__.__name__,
                attachments.c.record_id == self.record.id,
                attachments.c.name == self.definition.name,
            )
            .order_by(attachments.c.id)
        )
        return [Attachment(**row) for row in session.execute(query).mappings()]

    @property
    def blobs(self):
        pending = self.record._attachment_changes.get(self.definition.name)
        if pending is not None:
            return list(pending)
        return [attachment.blob for attachment in self.attachments]

    def attached(self):
        return bool(self.blobs)

    def blank(self):
        return not self.attached()

    def __bool__(self):
        return self.attached()

    def attach(self, *attachables, **options):
        if options:
            if attachables:
                raise TypeError("Pass an attachable or io/filename keywords, not both")
            attachables = (options,)
        if len(attachables) == 1 and isinstance(attachables[0], (tuple, list)):
            attachables = attachables[0]
        assign(self.record, self.definition.name, self.blobs + list(attachables))
        if (
            self.record.is_persisted()
            and not self.record._changes
            and not self.record.save()
        ):
            return None
        return self

    def _clear_change(self):
        if self.record.id is not None:
            defer_uploads(
                session,
                (self.record.__class__.__name__, self.record.id, self.definition.name),
                {},
                append=False,
            )
        self.record._attachment_changes.pop(self.definition.name, None)
        self.record._attachment_cache[self.definition.name] = []

    @transactional
    def detach(self):
        for attachment in self.attachments:
            attachment.detach()
        self._clear_change()

    @transactional
    def purge(self):
        attachments = self.attachments
        self._clear_change()
        for attachment in attachments:
            attachment.purge()

    @transactional
    def purge_later(self):
        attachments = self.attachments
        self._clear_change()
        for attachment in attachments:
            attachment.purge_later()

    def __iter__(self):
        if self.definition.name in self.record._attachment_changes:
            return iter(self.blobs)
        return iter(self.attachments)

    def __len__(self):
        return len(self.blobs)


class AttachedOne(AttachedMany):
    @property
    def attachment(self):
        return next(iter(self.attachments), None)

    @property
    def blob(self):
        return next(iter(self.blobs), None)

    def attach(self, attachable=None, **options):
        if options:
            if attachable is not None:
                raise TypeError("Pass an attachable or io/filename keywords, not both")
            attachable = options
        assign(self.record, self.definition.name, attachable)
        if (
            self.record.is_persisted()
            and not self.record._changes
            and not self.record.save()
        ):
            return None
        return self

    def __getattr__(self, name):
        blob = self.blob
        if blob is None:
            raise AttributeError(f"{self.definition.name} is not attached")
        return getattr(blob, name)
