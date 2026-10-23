import io
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from flaskteroids.attachments import Blob
from flaskteroids.attachments.schema import blobs
from flaskteroids.db import session
from flaskteroids.rich_text import Content
from tests.rich_text.app.models.note import Note

pytestmark = pytest.mark.usefixtures("app_ctx")


def test_abandoned_upload_cleanup_preserves_recent_and_attached_files(app):
    abandoned = Blob.create_and_upload(io=io.BytesIO(b"old"), filename="old.txt")
    recent = Blob.create_and_upload(io=io.BytesIO(b"recent"), filename="recent.txt")
    attached = Blob.create_and_upload(
        io=io.BytesIO(b"attached"), filename="attached.txt"
    )
    Note.create(content=Content().append_attachables([attached]))
    session.execute(
        update(blobs)
        .where(blobs.c.id.in_([abandoned.id, attached.id]))
        .values(
            created_at=datetime.now(UTC) - timedelta(days=3),
        )
    )
    session.commit()
    assert Blob.purge_unattached() == 1
    app.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
    assert Blob.find_signed(abandoned.signed_id()) is None
    assert recent.download() == b"recent"
    assert attached.download() == b"attached"


def test_cleanup_jobs_recheck_files_attached_after_the_sweep(app):
    blob = Blob.create_and_upload(io=io.BytesIO(b"retained"), filename="retained.txt")
    session.execute(
        update(blobs)
        .where(blobs.c.id == blob.id)
        .values(
            created_at=datetime.now(UTC) - timedelta(days=3),
        )
    )
    session.commit()
    assert Blob.purge_unattached() == 1
    Note.create(content=Content().append_attachables([blob]))
    app.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
    assert blob.download() == b"retained"
