"""Normalize HTML transports on the same request that Flask subsequently dispatches."""

import re
from urllib.parse import unquote_plus

from flask.ctx import RequestContext
from werkzeug.exceptions import BadRequest, HTTPException, MethodNotAllowed, NotFound

from flaskteroids._routing import HTTP_METHODS


class _StrictFormParser:
    def parse(self, *args, **kwargs):
        self.silent = False
        try:
            return super().parse(*args, **kwargs)
        except ValueError as error:
            raise BadRequest("Malformed form body.") from error


def _form_override(request):
    raw = None
    if request.mimetype == "application/x-www-form-urlencoded":
        raw = request.get_data(cache=True).decode("utf-8", errors="replace")
    parser_class = request.form_data_parser_class
    if not issubclass(parser_class, _StrictFormParser):
        request.form_data_parser_class = type(
            "OverrideFormParser", (_StrictFormParser, parser_class), {}
        )
    form = request.form
    if raw is not None and re.search(r"%(?![a-fA-F0-9]{2})", raw):
        raise BadRequest("Malformed form encoding.")

    # Werkzeug owns decoding/multipart parsing. This adapter handles Rack's
    # scalar-vs-container and nil-vs-empty transport distinctions only.
    entries = list(form.items(multi=True))
    if raw is not None:
        entries = []
        values_by_key = dict(form.lists())
        offsets = {}
        for pair in raw.split("&"):
            encoded_key, separator, _ = pair.partition("=")
            key = unquote_plus(encoded_key)
            values = values_by_key.get(key, ())
            offset = offsets.get(key, 0)
            if offset < len(values):
                entries.append((key, values[offset] if separator else None))
                offsets[key] = offset + 1
    value = None
    shape = None
    for key, entry in entries:
        if key == "_method":
            shape = "scalar" if entry is not None else None
            value = entry
        elif key.startswith("_method["):
            kind = "array" if key.startswith("_method[]") else "mapping"
            if shape is not None and shape != kind:
                raise BadRequest("Conflicting method override parameter shapes.")
            shape = kind
            value = ""  # A container blocks header fallback but is not a verb.
    if value is None and any(
        key == "_method" or key.startswith("_method[") for key in request.files
    ):
        return ""  # File-valued transport parameters also block header fallback.
    return value


class RoutingRequestContext(RequestContext):
    def match_request(self):
        routes = self.app.extensions.get("flaskteroids.routes")
        if routes is None:
            return super().match_request()

        adapter = self.url_adapter
        request = self.request
        managed = routes.matches_request(adapter, request.method)
        error = None
        if managed and request.method == "POST":
            try:
                override = _form_override(request)
            except HTTPException as caught:
                error = caught
                override = None
            if override is None:
                override = request.headers.get("X-HTTP-Method-Override", "")
            effective = override.upper()
            if effective in HTTP_METHODS:
                request.environ.setdefault("flaskteroids.original_method", "POST")
                request.environ["REQUEST_METHOD"] = effective
                request.method = effective
                adapter.default_method = effective
        if error is not None:
            request.environ["flaskteroids.routing_error"] = True
            request.routing_exception = error
            return
        super().match_request()
        if managed and isinstance(request.routing_exception, MethodNotAllowed):
            request.environ["flaskteroids.routing_error"] = True
            request.routing_exception = NotFound()
