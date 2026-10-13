from flask import current_app, url_for


def blob_path(
    attachment, *, disposition="inline", expires_in=None, route=None, _external=False
):
    if disposition not in {"inline", "attachment"}:
        raise ValueError("Disposition must be inline or attachment")
    blob = getattr(attachment, "blob", attachment)
    if blob is None:
        raise ValueError("No blob is attached")
    config = current_app.config.attachments
    route = route or config.resolve_model_to_route
    if route not in {"redirect", "proxy"}:
        raise ValueError("Attachment route must be redirect or proxy")
    if expires_in is None:
        expires_in = config.urls_expire_in
    return url_for(
        f"flaskteroids_attachments.{route}",
        signed_id=blob.signed_id(expires_in=expires_in),
        filename=blob.filename,
        **({"disposition": disposition} if disposition != "inline" else {}),
        _external=_external,
    )


def blob_url(attachment, **options):
    return blob_path(attachment, _external=True, **options)
