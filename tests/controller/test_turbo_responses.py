import pytest
from flask import Flask, Response
from markupsafe import Markup

from flaskteroids.actions import after_action, around_action, before_action
from flaskteroids.controller import Controller, init
from flaskteroids.exceptions import DoubleRenderError, ProgrammerError

STREAM_MIME = "text/vnd.turbo-stream.html"


@pytest.mark.parametrize(
    "path,accept,selected",
    [
        ("/response/", None, "html"),
        ("/response/", STREAM_MIME, "turbo_stream"),
        ("/response/", f"{STREAM_MIME}, text/html", "turbo_stream"),
        ("/response/", f"text/html, {STREAM_MIME}", "html"),
        ("/response/", f"application/json, {STREAM_MIME}, text/html", "json"),
        ("/response/", f"{STREAM_MIME};q=0.4, text/html;q=0.9", "html"),
        ("/response/", f"{STREAM_MIME};q=0.9, text/html;q=0.4", "turbo_stream"),
        ("/response/", f"{STREAM_MIME};q=0, text/html", "html"),
        ("/response/", "text/*", "html"),
        ("/response/", "*/*", "html"),
        ("/response/", "application/*", "json"),
        ("/response.turbo_stream", "application/json", "turbo_stream"),
        ("/response.turbo_stream/", "text/html", "turbo_stream"),
        ("/response.json", STREAM_MIME, "json"),
    ],
)
def test_stream_negotiation_preserves_quality_wildcards_and_explicit_formats(
    response_client, path, accept, selected
):
    events = []

    def action(controller):
        def handler(name):
            events.append(name)
            return name

        controller.respond_to(
            html=lambda: handler("html"),
            json=lambda: handler("json"),
            turbo_stream=lambda: handler("turbo_stream"),
        )

    response = response_client(action).get(
        path, headers={"Accept": accept} if accept else {}
    )
    assert events == [selected]
    assert response.text == selected
    if selected == "turbo_stream":
        assert response.mimetype == STREAM_MIME


@pytest.mark.parametrize(
    "path,accept,offered,status",
    [
        ("/response/", f"{STREAM_MIME}, text/html", "html", 200),
        ("/response/", "text/*", "turbo_stream", 200),
        ("/response/", None, "turbo_stream", 406),
        ("/response/", "application/xml", "turbo_stream", 406),
        ("/response/", STREAM_MIME, "html", 406),
        ("/response/", f"{STREAM_MIME};q=0, */*;q=0", "turbo_stream", 406),
        ("/response.turbo_stream", "text/html", "html", 406),
        ("/response.json", STREAM_MIME, "turbo_stream", 406),
    ],
)
def test_stream_negotiation_matches_only_offered_formats(
    response_client, render_template, path, accept, offered, status
):
    response = response_client(
        lambda controller: controller.respond_to(**{offered: lambda: "Offered"})
    ).get(path, headers={"Accept": accept} if accept else {})
    assert response.status_code == status
    render_template.assert_not_called()


@pytest.mark.parametrize(
    "returned", ["<turbo-stream></turbo-stream>", Markup("<b>ok</b>")]
)
def test_stream_handler_native_text_receives_stream_mime(response_client, returned):
    response = response_client(
        lambda controller: controller.respond_to(turbo_stream=lambda: returned)
    ).get("/response/", headers={"Accept": STREAM_MIME})
    assert response.mimetype == STREAM_MIME
    assert response.text == returned


@pytest.mark.parametrize(
    "returned",
    [
        Response("Native", status=202, mimetype="text/plain"),
        ("Native", 202, {"Content-Type": "text/plain"}),
    ],
)
def test_stream_handler_respects_explicit_native_response_metadata(
    response_client, returned
):
    response = response_client(
        lambda controller: controller.respond_to(turbo_stream=lambda: returned)
    ).get("/response/", headers={"Accept": STREAM_MIME})
    assert response.status_code == 202
    assert response.mimetype == "text/plain"
    assert response.text == "Native"


@pytest.mark.parametrize("container", [list, tuple])
def test_stream_render_joins_operations_and_escapes_untrusted_text(
    response_client, container
):
    def action(controller):
        controller.response.status_code = 201
        controller.response.headers["X-Pending"] = "retained"
        controller.render(
            turbo_stream=container(
                [
                    controller.turbo_stream.remove("old"),
                    "<script>unsafe</script>",
                    controller.turbo_stream.append("items", Markup("<b>New</b>")),
                ]
            )
        )

    response = response_client(action).get("/response/")
    assert response.status_code == 201
    assert response.headers["X-Pending"] == "retained"
    assert response.mimetype == STREAM_MIME
    assert response.text.count("<turbo-stream ") == 2
    assert "&lt;script&gt;unsafe&lt;/script&gt;" in response.text
    assert "<template><b>New</b></template>" in response.text


@pytest.mark.parametrize(
    "value,expected",
    [
        ("<b>Text</b>", "&lt;b&gt;Text&lt;/b&gt;"),
        (Markup("<b>Safe</b>"), "<b>Safe</b>"),
        ([], ""),
    ],
)
def test_explicit_stream_render_supports_single_or_empty_operations(
    response_client, value, expected
):
    response = response_client(
        lambda controller: controller.render(turbo_stream=value, status=422)
    ).get("/response/")
    assert response.status_code == 422
    assert response.mimetype == STREAM_MIME
    assert response.text == expected


@pytest.mark.parametrize(
    "args,kwargs",
    [
        (("show",), {"turbo_stream": "body"}),
        ((), {"json": None, "turbo_stream": "body"}),
        (("show",), {"json": None}),
        ((), {"turbo_stream": None}),
        ((), {"turbo_stream": [1]}),
    ],
)
def test_stream_render_rejects_conflicting_or_invalid_arguments(
    response_client, args, kwargs
):
    with pytest.raises(ProgrammerError):
        response_client(lambda controller: controller.render(*args, **kwargs)).get(
            "/response/"
        )


@pytest.mark.parametrize("second", ["stream", "json", "head", "respond_to"])
def test_stream_render_preserves_the_single_response_contract(response_client, second):
    def action(controller):
        controller.render(turbo_stream=controller.turbo_stream.remove("item"))
        if second == "stream":
            controller.render(turbo_stream="second")
        elif second == "json":
            controller.render(json={})
        elif second == "head":
            controller.head(204)
        else:
            controller.respond_to(turbo_stream=lambda: "second")

    with pytest.raises(DoubleRenderError):
        response_client(action).get("/response/")


@pytest.mark.parametrize("halt_before", [False, True])
def test_stream_responses_keep_callback_order_and_before_action_halting(halt_before):
    events = []

    class StreamsController(Controller):
        before_action("_before")
        around_action("_around")
        after_action("_after")

        def _before(self):
            events.append("before")
            if halt_before:
                self.respond_to(turbo_stream=lambda: self.turbo_stream.remove("old"))

        def _around(self):
            events.append("around:before")
            yield
            assert self.performed
            events.append("around:after")

        def show(self):
            events.append("action")
            self.render(turbo_stream=self.turbo_stream.remove("old"))

        def _after(self):
            events.append("after")
            self.response.headers["X-After"] = "present"

    init(StreamsController)
    app = Flask(__name__)
    app.add_url_rule("/streams", view_func=lambda: StreamsController().show())
    response = app.test_client().get("/streams", headers={"Accept": STREAM_MIME})
    assert response.mimetype == STREAM_MIME
    assert events == (
        ["before"]
        if halt_before
        else ["before", "around:before", "action", "around:after", "after"]
    )


@pytest.mark.parametrize(
    "header,expected", [(None, None), ("", None), ("  ", None), ("editor", "editor")]
)
def test_controller_frame_properties_identify_nonblank_frame_requests(header, expected):
    app = Flask(__name__)
    with app.test_request_context(
        headers={"Turbo-Frame": header} if header is not None else {}
    ):
        controller = Controller()
        assert controller.turbo_frame_request_id == expected
        assert controller.turbo_frame_request is (expected is not None)
        assert controller.layout == "layouts/application.html"
        assert controller.frame_layout == "layouts/turbo/frame.html"


def test_controller_frame_properties_are_safe_without_a_request():
    app = Flask(__name__)
    with app.app_context():
        controller = Controller()
    assert controller.turbo_frame_request_id is None
    assert not controller.turbo_frame_request
