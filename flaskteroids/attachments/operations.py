from flask import current_app
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from flaskteroids.attachments.schema import attachments, blobs
from flaskteroids.db import session


def upload_blob(blob, upload):
    upload.stream.seek(0)
    blob.service.upload(
        blob.key,
        upload.stream,
        checksum=blob.checksum,
        filename=blob.filename,
        **blob.serving_options(),
    )


def purge_blob(blob_id, key, service_name):
    if not _delete_metadata(session, blob_id, key, service_name):
        return False
    current_app.extensions["flaskteroids.attachments"].service(service_name).delete(key)
    return True


def purge_blob_after_commit(blob_id, key, service_name):
    database = current_app.extensions["flaskteroids.db"]
    with database.new_session() as purge_session, purge_session.begin():
        if not _delete_metadata(purge_session, blob_id, key, service_name):
            return False
    current_app.extensions["flaskteroids.attachments"].service(service_name).delete(key)
    return True


def _delete_metadata(db_session, blob_id, key, service_name):
    row = (
        db_session.execute(select(blobs).where(blobs.c.id == blob_id))
        .mappings()
        .first()
    )
    if row is not None:
        if row["key"] != key or row["service_name"] != service_name:
            return False
        attached = db_session.execute(
            select(attachments.c.id).where(attachments.c.blob_id == blob_id).limit(1)
        ).first()
        if attached is not None:
            return False
        try:
            with db_session.begin_nested():
                db_session.execute(delete(blobs).where(blobs.c.id == blob_id))
        except IntegrityError:
            return False
    return True
