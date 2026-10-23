import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from itsdangerous import BadSignature
from markupsafe import escape
from sqlalchemy import select

from flaskteroids.attachments.attached import AttachedMany
from flaskteroids.attachments.blob import Attachment, Blob
from flaskteroids.attachments.schema import attachments, blobs
from flaskteroids.attachments.signatures import verified_token
from flaskteroids.attachments.urls import blob_path
from flaskteroids.db import session
from flaskteroids.exceptions import StrictLoadingViolationError

_PREVIEW_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/avif"}


@dataclass(frozen=True)
class Reference:
    sgid: str
    caption: str = ""


class Fragment(HTMLParser):
    """Split an HTML5-sanitized fragment into markup and attachment references."""

    def __init__(self, html):
        super().__init__(convert_charrefs=False)
        self.parts = []
        self.skipping = None
        self.depth = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if self.skipping:
            if tag == self.skipping:
                self.depth += 1
            return
        options = dict(attrs)
        if tag in {"figure", "action-text-attachment"}:
            sgid, caption = options.get("sgid"), options.get("caption", "")
            if tag == "figure":
                try:
                    attachment = json.loads(options.get("data-trix-attachment", "{}"))
                    extra = json.loads(options.get("data-trix-attributes", "{}"))
                except (ValueError, TypeError, RecursionError):
                    attachment, extra = {}, {}
                if isinstance(attachment, dict) and isinstance(extra, dict):
                    sgid = attachment.get("sgid")
                    caption = extra.get("caption", attachment.get("caption", ""))
            if isinstance(sgid, str) and isinstance(caption, str):
                caption = caption.encode("utf-8", errors="replace").decode()
                self.parts.append(Reference(sgid, caption))
            self.skipping, self.depth = tag, 1
            return
        self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if self.skipping:
            if tag == self.skipping:
                self.depth -= 1
                if not self.depth:
                    self.skipping = None
            return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)

    def handle_entityref(self, name):
        if not self.skipping:
            self.parts.append(f"&{name};")

    def handle_charref(self, name):
        if not self.skipping:
            self.parts.append(f"&#{name};")


def resolve(references, record=None):
    identities = {}
    for reference in references:
        if "." not in reference.sgid or not re.fullmatch(
            r"[A-Za-z0-9_.-]{1,4096}", reference.sgid
        ):
            continue
        try:
            payload = verified_token("rich_text_attachable", reference.sgid)
            if type(payload.get("id")) is int and isinstance(payload.get("key"), str):
                identities[reference.sgid] = (payload["id"], payload["key"])
        except BadSignature:
            continue
    if not identities:
        return {}
    cached = None if record is None else record._attachment_cache.get("embeds")
    if cached is None and record is not None:
        if (
            record._definition.strict_loading
            and not record._changes
            and record.is_persisted()
        ):
            raise StrictLoadingViolationError(
                f"{record.record_type}.{record.name} embeds must be eager loaded. "
                f"Use with_rich_text_{record.name}_and_embeds()."
            )
    found = {entry.blob.id: entry.blob for entry in cached or []}
    missing = {identity for identity, key in identities.values()} - found.keys()
    if cached is not None and record is not None and not record._changes:
        missing = set()
    if missing:
        found.update(
            (row["id"], Blob(**row))
            for row in session.execute(
                select(blobs).where(blobs.c.id.in_(missing))
            ).mappings()
        )
    return {
        token: found[identity]
        for token, (identity, key) in identities.items()
        if identity in found and found[identity].key == key
    }


def canonical(reference):
    return f'<action-text-attachment sgid="{escape(reference.sgid)}" caption="{escape(reference.caption)}"></action-text-attachment>'


def previewable(blob):
    return (
        blob.content_type in _PREVIEW_TYPES
        and blob.serving_options()["disposition"] == "inline"
    )


def render(reference, blob, *, editor=False):
    url = blob_path(blob)
    caption = reference.caption or blob.filename
    image = (
        f'<img src="{escape(url)}" alt="{escape(caption)}" loading="lazy">'
        if previewable(blob)
        else ""
    )
    attrs = ""
    if editor:
        metadata = {
            "sgid": reference.sgid,
            "filename": blob.filename,
            "filesize": blob.byte_size,
            "contentType": blob.content_type,
            "url": url,
            "href": url,
        }
        attrs = f' data-trix-attachment="{escape(json.dumps(metadata))}" data-trix-attributes="{escape(json.dumps({"caption": reference.caption}))}"'
    kind = "preview" if image else "file"
    return (
        f'<figure class="attachment attachment--{kind}"{attrs}>'
        f'<a href="{escape(url)}">{image or escape(blob.filename)}</a>'
        f'<figcaption class="attachment__caption">{escape(caption)}</figcaption></figure>'
    )


def preload_rows(rows):
    by_id = {row.id: row for row in rows if row.is_persisted()}
    for row in by_id.values():
        row._attachment_cache["embeds"] = []
    if not by_id:
        return
    query = (
        select(
            attachments,
            *(column.label("embedded_blob_" + column.name) for column in blobs.c),
        )
        .join(blobs, blobs.c.id == attachments.c.blob_id)
        .where(
            attachments.c.record_type == "RichText",
            attachments.c.name == "embeds",
            attachments.c.record_id.in_(by_id),
        )
        .order_by(attachments.c.id)
    )
    for item in session.execute(query).mappings():
        blob = Blob(
            **{column.name: item["embedded_blob_" + column.name] for column in blobs.c}
        )
        attachment = Attachment(
            **{column.name: item[column.name] for column in attachments.c}, _blob=blob
        )
        by_id[attachment.record_id]._attachment_cache["embeds"].append(attachment)


def preload(records, names):
    rows = []
    for owner in records:
        for name in names:
            row = getattr(owner, f"rich_text_{name}")
            if row is not None:
                row._record = owner
                rows.append(row)
    preload_rows(rows)
    return records


class EmbeddedFiles(AttachedMany):
    @property
    def attachments(self):
        cached = self.record._attachment_cache.get("embeds")
        if cached is not None:
            return list(cached)
        if self.record._definition.strict_loading and self.record.is_persisted():
            raise StrictLoadingViolationError("Rich-text embeds must be eager loaded")
        return super().attachments
