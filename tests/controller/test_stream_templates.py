import pytest
from flask import Flask
from flask import render_template as flask_render_template
from jinja2 import DictLoader, TemplateNotFound

from flaskteroids.actions import after_action, around_action
from flaskteroids.controller import ActionController, init

STREAM_MIME = "text/vnd.turbo-stream.html"
TURBO_ACCEPT = f"{STREAM_MIME}, text/html, application/xhtml+xml"


@pytest.fixture(autouse=True)
def render_template(mocker):
    return mocker.patch(
        "flaskteroids.controller.render_template", wraps=flask_render_template
    )


@pytest.fixture
def stream_client():
    def build(action=None, templates=None):
        class PostsController(ActionController):
            def show(self):
                self.title = "Assigned title"
                if action:
                    return action(self)

        init(PostsController)
        app = Flask(__name__)
        app.testing = True
        app.jinja_loader = DictLoader(templates or {})
        for path in ("/posts", "/posts.turbo_stream", "/posts.json"):
            app.add_url_rule(
                path,
                endpoint=path,
                view_func=lambda: PostsController().show(),
                methods=["GET", "POST"],
                strict_slashes=False,
            )
        return app.test_client()

    return build


@pytest.mark.parametrize(
    "path,accept,mime,body",
    [
        ("/posts", None, "text/html", "HTML Assigned title"),
        ("/posts", "*/*", "text/html", "HTML Assigned title"),
        ("/posts", TURBO_ACCEPT, STREAM_MIME, "Stream Assigned title"),
        ("/posts", STREAM_MIME, STREAM_MIME, "Stream Assigned title"),
        ("/posts.turbo_stream/", "text/html", STREAM_MIME, "Stream Assigned title"),
        ("/posts.json", STREAM_MIME, "text/html", "HTML Assigned title"),
    ],
)
def test_implicit_templates_follow_stream_negotiation_and_explicit_suffix(
    stream_client, path, accept, mime, body
):
    client = stream_client(
        templates={
            "posts/show.html": "HTML {{ title }}",
            "posts/show.turbo_stream.html": "Stream {{ title }}",
        }
    )
    response = client.get(path, headers={"Accept": accept} if accept else {})
    assert response.mimetype == mime
    assert response.text == body


@pytest.mark.parametrize("explicit", [False, True])
def test_stream_handlers_can_leave_the_stream_template_implicit(
    stream_client, explicit
):
    def action(controller):
        controller.respond_to(
            turbo_stream=(lambda: controller.render("show"))
            if explicit
            else lambda: None
        )

    response = stream_client(
        action,
        {"posts/show.turbo_stream.html": "Stream {{ title }}"},
    ).get("/posts", headers={"Accept": STREAM_MIME})
    assert response.mimetype == STREAM_MIME
    assert response.text == "Stream Assigned title"


def test_html_handler_keeps_implicit_html_when_stream_was_not_offered(stream_client):
    response = stream_client(
        lambda controller: controller.respond_to(html=lambda: None),
        {
            "posts/show.html": "HTML",
            "posts/show.turbo_stream.html": "Stream",
        },
    ).get("/posts", headers={"Accept": TURBO_ACCEPT})
    assert response.mimetype == "text/html"
    assert response.text == "HTML"


@pytest.mark.parametrize("action", [None, "new", "admin/posts/new"])
def test_turbo_post_uses_html_fallback_and_preserves_validation_status(
    stream_client, action
):
    template = action if action and "/" in action else f"posts/{action or 'show'}"
    response = stream_client(
        lambda controller: controller.render(action, status=422),
        {f"{template}.html": "Invalid {{ title }}"},
    ).post("/posts", headers={"Accept": TURBO_ACCEPT})
    assert response.status_code == 422
    assert response.mimetype == "text/html"
    assert response.text == "Invalid Assigned title"


@pytest.mark.parametrize(
    "path,accept",
    [
        ("/posts.turbo_stream", TURBO_ACCEPT),
        ("/posts", STREAM_MIME),
        ("/posts", f"{STREAM_MIME}, text/html;q=0"),
    ],
)
def test_missing_stream_template_does_not_fallback_when_html_is_disallowed(
    stream_client, path, accept
):
    client = stream_client(templates={"posts/show.html": "HTML"})
    with pytest.raises(TemplateNotFound) as exc:
        client.get(path, headers={"Accept": accept})
    assert exc.value.name == "posts/show.turbo_stream.html"


@pytest.mark.parametrize(
    "dependency", ["{% include 'missing.html' %}", "{% extends 'missing.html' %}"]
)
def test_stream_template_dependency_failures_are_not_treated_as_missing_roots(
    stream_client, dependency
):
    client = stream_client(
        templates={
            "posts/show.html": "HTML fallback",
            "posts/show.turbo_stream.html": dependency,
        }
    )
    with pytest.raises(TemplateNotFound) as exc:
        client.get("/posts", headers={"Accept": TURBO_ACCEPT})
    assert exc.value.name == "missing.html"


def test_controller_stream_partial_shares_assigns_and_explicit_locals(stream_client):
    class Record:
        def to_key(self):
            return [7]

        def to_partial_path(self):
            return "posts/post"

    def action(controller):
        controller.render(
            turbo_stream=controller.turbo_stream.append(
                "items", Record(), locals={"label": "<Entered>"}
            )
        )

    response = stream_client(
        action,
        {"posts/_post.html": "<p>{{ title }} {{ label }} {{ post.to_key()[0] }}</p>"},
    ).get("/posts")
    assert response.mimetype == STREAM_MIME
    assert "<p>Assigned title &lt;Entered&gt; 7</p>" in response.text


def test_implicit_stream_render_precedes_around_cleanup_and_after_callbacks():
    events = []

    class StreamsController(ActionController):
        around_action("_around")
        after_action("_after")

        def _around(self):
            events.append("around:before")
            yield
            assert self.performed
            assert self.response.mimetype == STREAM_MIME
            events.append("around:after")

        def show(self):
            events.append("action")
            self.respond_to(turbo_stream=lambda: None)

        def _after(self):
            events.append("after")
            self.response.headers["X-After"] = "present"

    init(StreamsController)
    app = Flask(__name__)
    app.testing = True
    app.jinja_loader = DictLoader(
        {"streams/show.turbo_stream.html": "{{ rendered() }}"}
    )

    def rendered():
        events.append("render")
        return "Stream body"

    app.jinja_env.globals["rendered"] = rendered
    app.add_url_rule("/streams", view_func=lambda: StreamsController().show())
    response = app.test_client().get("/streams", headers={"Accept": STREAM_MIME})
    assert response.text == "Stream body"
    assert response.headers["X-After"] == "present"
    assert events == ["around:before", "action", "render", "around:after", "after"]


def test_layout_assign_is_selected_by_context_processor_instead_of_raw_instance(
    stream_client,
):
    def action(controller):
        controller.layout = "custom/layout.html"

    client = stream_client(action, {"posts/show.html": "{{ layout }}"})

    @client.application.context_processor
    def layout_context():
        return {"layout": "selected/layout.html"}

    response = client.get("/posts")
    assert response.text == "selected/layout.html"
