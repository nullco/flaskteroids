"""HTTP error responses, preserving Flask's exception handling and headers."""

from http import HTTPStatus

from werkzeug.exceptions import HTTPException, default_exceptions

from flaskteroids._request_policy import request_policy
from flaskteroids.attachments import UploadTooLarge
from flaskteroids.exceptions import (
    InvalidParameter,
    MissingParameter,
    RecordInvalid,
    RecordNotFoundException,
)


def register_error_handlers(app, default_policy):
    def render_error(error):
        return request_policy(default_policy).error_response(error)

    def handle_error(code):
        def handle(error):
            return render_error(default_exceptions[code](description=str(error)))

        return handle

    for exception, code in (
        (MissingParameter, HTTPStatus.BAD_REQUEST),
        (InvalidParameter, HTTPStatus.BAD_REQUEST),
        (RecordNotFoundException, HTTPStatus.NOT_FOUND),
        (RecordInvalid, HTTPStatus.UNPROCESSABLE_ENTITY),
        (UploadTooLarge, HTTPStatus.REQUEST_ENTITY_TOO_LARGE),
    ):
        app.register_error_handler(exception, handle_error(code))
    app.register_error_handler(HTTPException, render_error)
