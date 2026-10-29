"""Application-wide POST transport normalization, before Flask routing."""

import re
import sys
from contextlib import contextmanager, suppress
from urllib.parse import unquote_plus

from flask import current_app, has_app_context
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest
from werkzeug.sansio.multipart import Epilogue, Field, File, MultipartDecoder, NeedData

from flaskteroids._routing import HTTP_METHODS

PREPARED_REQUEST = "flaskteroids.prepared_request"
TRANSPORT_ERROR = "flaskteroids.transport_error"
FORM_PAIRS = "flaskteroids.form_pairs"
APP_CONTEXT = "flaskteroids.middleware_app_context"
TEARDOWN_ERROR = "flaskteroids.teardown_error"


@contextmanager
def _application_context(application, environ):
    if has_app_context() and current_app._get_current_object() is application:
        yield
        return
    context = application.app_context()
    context.push()
    environ[APP_CONTEXT] = True
    try:
        yield
    finally:
        error = environ.pop(TEARDOWN_ERROR, sys.exception())
        environ.pop(APP_CONTEXT, None)
        context.pop(error)


class _MultipartOrderStream:
    """Observe dependency-decoded part names, without buffering upload bodies."""

    def __init__(self, stream, boundary, parser, parts):
        self.stream = stream
        self.parts = parts
        self.decoder = MultipartDecoder(
            boundary,
            max_form_memory_size=parser.max_form_memory_size,
            max_parts=parser.max_form_parts,
        )

    def read(self, size=-1):
        data = self.stream.read(size)
        self.decoder.receive_data(data or None)
        while True:
            event = self.decoder.next_event()
            if isinstance(event, (NeedData, Epilogue)):
                break
            if isinstance(event, (Field, File)):
                self.parts.append((event.name, isinstance(event, File)))
        return data

    def __getattr__(self, name):
        return getattr(self.stream, name)


class _TransportFormParser:
    def parse(self, *args, **kwargs):
        self.silent = False
        streams = []
        factory = self.stream_factory

        def track_stream(*args, **kwargs):
            stream = factory(*args, **kwargs)
            streams.append(stream)
            return stream

        self.stream_factory = track_stream
        try:
            return super().parse(*args, **kwargs)
        except BaseException as error:
            for stream in streams:
                with suppress(OSError):
                    stream.close()
            if isinstance(error, ValueError):
                raise BadRequest("Malformed form body.") from error
            raise
        finally:
            self.stream_factory = factory

    def _parse_multipart(self, stream, mimetype, content_length, options):
        boundary = options.get("boundary", "").encode("ascii")
        observer = _MultipartOrderStream(stream, boundary, self, self.parts)
        _, form, files = super()._parse_multipart(
            observer, mimetype, content_length, options
        )
        return stream, form, files


def _form_pairs(request):
    if request.mimetype not in {
        "",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    }:
        return None

    original_type = request.environ.get("CONTENT_TYPE")
    parser_class = request.form_data_parser_class
    parts = []
    request.form_data_parser_class = type(
        "TransportFormParser", (_TransportFormParser, parser_class), {"parts": parts}
    )
    try:
        if not request.mimetype:
            request.environ["CONTENT_TYPE"] = "application/x-www-form-urlencoded"
            request.__dict__.pop("_parsed_content_type", None)
        raw = None
        if request.mimetype == "application/x-www-form-urlencoded":
            raw = request.get_data(cache=True).decode("utf-8", errors="replace")
        form, files = request.form, request.files
        if raw is not None:
            if re.search(r"%(?![a-fA-F0-9]{2})", raw):
                raise BadRequest("Malformed form encoding.")
            parts = []
            for pair in raw.split("&"):
                key, separator, _ = pair.partition("=")
                parts.append((unquote_plus(key), False, bool(separator)))
        else:
            parts = [(key, is_file, True) for key, is_file in parts]

        entries = []
        offsets = {}
        sources = {False: dict(form.lists()), True: dict(files.lists())}
        for key, is_file, has_value in parts:
            values = sources[is_file].get(key, ())
            offset_key = (key, is_file)
            offset = offsets.get(offset_key, 0)
            if offset < len(values):
                entries.append((key, values[offset] if has_value else None))
                offsets[offset_key] = offset + 1
        # Keep additions made by an application-owned parser as well.
        for is_file, source in ((False, form), (True, files)):
            for key, values in source.lists():
                entries.extend(
                    (key, value) for value in values[offsets.get((key, is_file), 0) :]
                )
        return entries
    finally:
        request.form_data_parser_class = parser_class
        if original_type is None:
            request.environ.pop("CONTENT_TYPE", None)
        else:
            request.environ["CONTENT_TYPE"] = original_type
        request.__dict__.pop("_parsed_content_type", None)


def _override(entries):
    value = None
    shape = None
    for key, entry in entries:
        if key == "_method":
            if isinstance(entry, FileStorage):
                shape, value = "mapping", ""
            else:
                shape = "scalar" if entry is not None else None
                value = entry
        elif key.startswith("_method["):
            kind = "array" if key.startswith("_method[]") else "mapping"
            if shape is not None and shape != kind:
                raise BadRequest("Conflicting method override parameter shapes.")
            shape, value = kind, ""
    return value


class MethodOverrideMiddleware:
    def __init__(self, app, *, application):
        self.application = application
        self.app = app

    def __call__(self, environ, start_response):
        if environ.get("REQUEST_METHOD") != "POST":
            return self.app(environ, start_response)

        application = self.application
        with _application_context(application, environ):
            request = application.request_class(environ)
            request.json_module = application.json
            environ[PREPARED_REQUEST] = request
            try:
                try:
                    entries = _form_pairs(request)
                    if entries is not None:
                        environ[FORM_PAIRS] = entries
                    override = _override(entries or ())
                except Exception as error:  # noqa: BLE001 -- Flask handles it after adoption.
                    environ[TRANSPORT_ERROR] = error
                    override = None
                if override is None:
                    override = request.headers.get("X-HTTP-Method-Override", "")
                effective = override.upper()
                if effective in HTTP_METHODS:
                    environ["flaskteroids.original_method"] = "POST"
                    environ["REQUEST_METHOD"] = effective
                    request.method = effective
                return self.app(environ, start_response)
            finally:
                # Flask adopts the request and owns its normal/streaming cleanup.
                # If dispatch never adopted it, middleware still owns the files.
                if environ.pop(PREPARED_REQUEST, None) is request:
                    request.close()
