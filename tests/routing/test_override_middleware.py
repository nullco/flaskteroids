from io import BytesIO

import pytest
from flask import Flask, Request, Response, g, request, session, stream_with_context
from flask.sessions import SecureCookieSessionInterface
from werkzeug.formparser import FormDataParser
from werkzeug.routing import BaseConverter


@pytest.fixture
def multipart_body():
    def encode(parts):
        chunks = []
        for name, value in parts:
            header = (
                f'--routing-boundary\r\nContent-Disposition: form-data; name="{name}"'
            )
            if isinstance(value, tuple):
                filename, data = value
                header += f'; filename="{filename}"'
            else:
                data = value.encode()
            chunks.extend((header.encode(), b"\r\n\r\n", data, b"\r\n"))
        chunks.append(b"--routing-boundary--\r\n")
        return b"".join(chunks)

    return encode


@pytest.fixture
def upload_streams(routing_app):
    streams = []

    class RecordingParser(FormDataParser):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            factory = self.stream_factory

            def record(*args, **kwargs):
                stream = factory(*args, **kwargs)
                streams.append(stream)
                return stream

            self.stream_factory = record

    class UploadRequest(Request):
        form_data_parser_class = RecordingParser

    routing_app.request_class = UploadRequest
    return streams


@pytest.mark.parametrize(
    "parts,status,action,override",
    [
        (
            [("_method[x]", "1"), ("_method", "PUT"), ("_method[x]", "2")],
            400,
            None,
            None,
        ),
        ([("_method", "PUT"), ("_method", "DELETE")], 200, "destroy", "DELETE"),
        ([("_method[x]", "1"), ("_method", "DELETE")], 200, "destroy", "DELETE"),
        (
            [("_method", ("method.txt", b"PUT")), ("_method", "DELETE")],
            200,
            "destroy",
            "DELETE",
        ),
        (
            [("_method", "DELETE"), ("_method", ("method.txt", b"PUT"))],
            200,
            "create",
            {"filename": "method.txt", "content": "PUT"},
        ),
        (
            [("_method", "PUT"), ("_method[x]", ("method.txt", b"DELETE"))],
            400,
            None,
            None,
        ),
    ],
)
def test_multipart_overrides_follow_wire_order(
    routing_app, multipart_body, parts, status, action, override
):
    response = routing_app.test_client().post(
        "/probe",
        data=multipart_body(parts),
        content_type="multipart/form-data; boundary=routing-boundary",
    )
    assert response.status_code == status
    if action is not None:
        assert response.json["action"] == action
        assert response.json["params"]["_method"] == override


@pytest.mark.parametrize("outcome", ["success", "csrf", "route", "malformed"])
def test_upload_streams_close_after_dispatch_and_early_failures(
    routing_app, upload_streams, multipart_body, outcome
):
    routing_app.config.controller.allow_forgery_protection = outcome == "csrf"
    body = multipart_body(
        [("image", ("image.txt", b"x" * 150_000)), ("_method", "DELETE")]
    )
    if outcome == "malformed":
        body = body[:-12]
    response = routing_app.test_client().post(
        "/products" if outcome == "route" else "/probe",
        data=body,
        content_type="multipart/form-data; boundary=routing-boundary",
    )
    assert (
        response.status_code
        == {"success": 200, "csrf": 400, "route": 404, "malformed": 400}[outcome]
    )
    assert upload_streams
    assert all(stream.closed for stream in upload_streams)


def test_override_reuses_the_configured_request_and_parser(routing_app):
    events = []

    class RecordingParser(FormDataParser):
        def parse(self, *args, **kwargs):
            events.append("parse")
            return super().parse(*args, **kwargs)

    class RecordingRequest(Request):
        form_data_parser_class = RecordingParser

        def __init__(self, *args, **kwargs):
            events.append("request")
            super().__init__(*args, **kwargs)

    routing_app.request_class = RecordingRequest
    response = routing_app.test_client().post("/probe", data={"_method": "DELETE"})
    assert response.json["action"] == "destroy"
    assert events == ["request", "parse"]


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_request_and_application_teardown_run_once(routing_app, method):
    events = []
    routing_app.teardown_request(lambda error: events.append("request"))
    routing_app.teardown_appcontext(lambda error: events.append("application"))
    response = routing_app.test_client().open("/probe", method=method)
    assert response.status_code == 200
    assert events == ["request", "application"]


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_application_teardown_receives_handled_dispatch_errors(routing_app, method):
    errors = []
    routing_app.config["PROPAGATE_EXCEPTIONS"] = False
    routing_app.teardown_appcontext(lambda error: errors.append(error))

    @routing_app.route("/failing", methods=["GET", "POST"])
    def failing():
        raise RuntimeError("Action failed")

    response = routing_app.test_client().open("/failing", method=method)
    assert response.status_code == 500
    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)


def test_session_loading_and_callbacks_observe_the_effective_method(routing_app):
    events = []

    class RecordingSessionInterface(SecureCookieSessionInterface):
        def open_session(self, app, incoming):
            events.append(("session", incoming.method))
            return super().open_session(app, incoming)

    routing_app.session_interface = RecordingSessionInterface()

    @routing_app.before_request
    def observe():
        events.append(("callback", request.method))

    response = routing_app.test_client().post("/probe", data={"_method": "DELETE"})
    assert response.json["action"] == "destroy"
    assert events == [("session", "DELETE"), ("callback", "DELETE")]


@pytest.mark.parametrize("transport", ["get", "post", "override"])
def test_native_converters_run_once_with_request_and_session_context(
    routing_app, transport
):
    calls = []

    class SessionConverter(BaseConverter):
        def to_python(self, value):
            calls.append(value)
            return f"{session['prefix']}:{value}:{request.method}"

    routing_app.url_map.converters["session_value"] = SessionConverter

    @routing_app.route(
        "/native/<session_value:value>", methods=["GET", "POST", "DELETE"]
    )
    def native(value):
        return {"value": value}

    client = routing_app.test_client()
    with client.session_transaction() as current:
        current["prefix"] = "authenticated"
    response = (
        client.get("/native/item")
        if transport == "get"
        else client.post(
            "/native/item",
            data={"_method": "DELETE"} if transport == "override" else {},
        )
    )
    expected = {"get": "GET", "post": "POST", "override": "DELETE"}[transport]
    assert response.json == {"value": f"authenticated:item:{expected}"}
    assert calls == ["item"]


def test_multipart_transport_is_read_once_without_rewinding(
    routing_app, multipart_body
):
    body = multipart_body(
        [("_method", "DELETE"), ("image", ("image.txt", b"upload bytes"))]
    )

    class ReadOnceInput(BytesIO):
        bytes_read = 0

        def read(self, size=-1):
            data = super().read(size)
            self.bytes_read += len(data)
            return data

        def readinto(self, buffer):
            count = super().readinto(buffer)
            self.bytes_read += count
            return count

        def seek(self, *args):
            pytest.fail("Normalization must not rewind the WSGI input")

    source = ReadOnceInput(body)
    response = routing_app.test_client().post(
        "/probe",
        environ_overrides={
            "wsgi.input": source,
            "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": "multipart/form-data; boundary=routing-boundary",
        },
    )
    assert response.json["params"]["image"]["content"] == "upload bytes"
    assert source.bytes_read == len(body)


def test_request_subclass_limits_apply_before_normalization(routing_app):
    class LimitedRequest(Request):
        @property
        def max_content_length(self):
            return 32 if self.path == "/probe" else super().max_content_length

    routing_app.request_class = LimitedRequest
    client = routing_app.test_client()
    values = {"_method": "PATCH", "title": "x" * 100}
    assert client.post("/probe", data=values).status_code == 413
    assert client.post("/products/1", data=values).json["action"] == "update"


def test_native_post_only_route_rejects_an_unroutable_override(routing_app):
    @routing_app.post("/native")
    def native():
        pytest.fail("The effective DELETE must not fall back to POST")

    assert (
        routing_app.test_client()
        .post("/native", data={"_method": "DELETE"})
        .status_code
        == 405
    )


def test_plain_flask_app_retains_its_own_transport_policy():
    app = Flask(__name__)

    @app.post("/native")
    def native():
        return {"method": request.method, "override": request.form["_method"]}

    assert app.test_client().post("/native", data={"_method": "DELETE"}).json == {
        "method": "POST",
        "override": "DELETE",
    }


def test_missing_content_type_is_parsed_as_a_post_form(routing_app):
    response = routing_app.test_client().post(
        "/probe",
        data=b"_method=PUT&title=kept",
        headers={"X-HTTP-Method-Override": "DELETE"},
    )
    assert response.json["action"] == "update"
    assert response.json["params"] == {"_method": "PUT", "title": "kept"}


def test_native_json_body_remains_available_after_header_override(routing_app):
    @routing_app.delete("/native")
    def native():
        return request.get_json()

    response = routing_app.test_client().post(
        "/native", json={"title": "kept"}, headers={"X-HTTP-Method-Override": "DELETE"}
    )
    assert response.json == {"title": "kept"}


def test_early_parser_errors_use_application_error_handlers(routing_app):
    @routing_app.errorhandler(400)
    def bad_request(error):
        return {"error": "invalid form", "method": request.method}, 400

    response = routing_app.test_client().post("/probe", data="_method=%ZZ")
    assert response.status_code == 400
    assert response.json == {"error": "invalid form", "method": "POST"}


def test_unexpected_parser_failures_use_flask_error_handling(routing_app):
    class FailingParser(FormDataParser):
        def parse(self, *args, **kwargs):
            raise RuntimeError("Application parser failed")

    class FailingRequest(Request):
        form_data_parser_class = FailingParser

    routing_app.request_class = FailingRequest
    routing_app.config["PROPAGATE_EXCEPTIONS"] = False

    @routing_app.errorhandler(500)
    def server_error(error):
        return {"error": "parser failure"}, 500

    response = routing_app.test_client().post("/probe", data={"_method": "DELETE"})
    assert response.status_code == 500
    assert response.json == {"error": "parser failure"}


def test_streaming_response_retains_the_effective_request_context(routing_app):
    @routing_app.delete("/native")
    def native():
        g.title = request.form["title"]
        session["seen"] = request.method

        @stream_with_context
        def generate():
            yield g.title
            yield f":{request.method}:{session['seen']}"

        return Response(generate())

    response = routing_app.test_client().post(
        "/native", data={"_method": "DELETE", "title": "kept"}
    )
    assert response.text == "kept:DELETE:DELETE"
    response.close()
