import hmac

from flask import Blueprint, abort, current_app, jsonify, request, session, url_for
from itsdangerous import BadSignature

from flaskteroids.attachments import Blob
from flaskteroids.attachments.services import StorageError, UploadTooLarge
from flaskteroids.attachments.signatures import signed_token, verified_token
from flaskteroids.attachments.urls import blob_path
from flaskteroids.csrf import CSRFToken
from flaskteroids.declarations import model_for


def upload_attributes(record, name):
    if name not in model_for(type(record)).rich_texts:
        return {}
    current_app.extensions["flaskteroids.db"].require_model(type(record))
    # The capability belongs to the rendered, authorized form and browser
    # session. It is not a public, unauthenticated arbitrary-file upload API.
    CSRFToken(current_app.secret_key).generate()
    token = signed_token(
        "rich_text_upload",
        {
            "record_type": type(record).__name__,
            "record_id": record.id if record.is_persisted() else None,
            "name": name,
            "nonce": session["csrf_nonce"],
        },
        current_app.config.rich_text.upload_token_expires_in,
    )
    return {"data-upload-url": url_for("flaskteroids_rich_text.upload", token=token)}


def init_rich_text(app):
    blueprint = Blueprint("flaskteroids_rich_text", __name__)

    @blueprint.post("/flaskteroids/rich_text/uploads/<token>")
    def upload(token):
        try:
            payload = verified_token("rich_text_upload", token)
        except BadSignature:
            abort(404)
        nonce = session.get("csrf_nonce")
        expected = payload.get("nonce")
        if (
            not isinstance(nonce, str)
            or not isinstance(expected, str)
            or not hmac.compare_digest(nonce, expected)
        ):
            abort(404)
        model = current_app.extensions["flaskteroids.db"].models.get(
            payload.get("record_type")
        )
        name = payload.get("name")
        identity = payload.get("record_id")
        if (
            model is None
            or not isinstance(name, str)
            or name not in model_for(model).rich_texts
            or (identity is not None and type(identity) is not int)
        ):
            abort(404)
        authorize = current_app.config.rich_text.authorize_upload
        if authorize is not None and not authorize(model, identity, name):
            abort(404)
        file = request.files.get("file")
        if file is None or not file.filename:
            abort(400, "A file upload is required")
        try:
            blob = Blob.create_and_upload(
                io=file.stream, filename=file.filename, content_type=file.content_type
            )
        except StorageError as error:
            if isinstance(error, UploadTooLarge):
                raise
            abort(400, "Invalid file upload")
        response = jsonify(
            {
                "sgid": blob.attachable_sgid,
                "url": blob_path(blob),
                "href": blob_path(blob),
                "filename": blob.filename,
                "filesize": blob.byte_size,
                "contentType": blob.content_type,
            }
        )
        response.headers["Cache-Control"] = "private, no-store"
        return response, 201

    app.register_blueprint(blueprint)
