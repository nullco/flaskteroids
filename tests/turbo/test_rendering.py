import pytest
from flask import render_template, render_template_string
from jinja2 import DictLoader, TemplateNotFound
from markupsafe import Markup

from flaskteroids.controller import helper, init
from flaskteroids.helpers import render
from flaskteroids.turbo import turbo_stream
from tests.app.models.user import User
from tests.assertions import HTML
from tests.turbo.fixtures.records import Post
from tests.views.fixtures.controllers.posts_controller import PostsController


@pytest.fixture
def partial_app(view_app_factory):
    app = view_app_factory()
    app.jinja_loader = DictLoader(
        {
            "posts/_post.html": '<article id="{{ dom_id(post) }}">{{ post.title }}</article>',
            "posts/_details.html": "<b>{{ item.title }}:{{ options.label }}</b>",
            "users/_user.html": "<p>{{ user.username }}</p>",
            "exact/file.html": "<i>{{ title }}</i>",
        }
    )
    return app


def test_render_record_uses_its_partial_path_and_local(partial_app, post):
    post.title = "<Reader>"
    with partial_app.app_context():
        result = render(post)
    assert isinstance(result, Markup)
    assert HTML(result).has("article", id="post_1")
    assert "&lt;Reader&gt;" in result


def test_render_mapped_record_uses_public_model_partial_protocol(app):
    app.jinja_loader = DictLoader({"users/_user.html": "<p>{{ user.username }}</p>"})
    with app.app_context():
        assert HTML(render(User(username="Reader"))).text == "Reader"


@pytest.mark.parametrize(
    "path", ["posts/details", "posts/_details", "posts/details.html"]
)
def test_render_explicit_partial_accepts_dict_locals(partial_app, path):
    with partial_app.app_context():
        result = render(
            partial=path,
            locals={"item": {"title": "<Post>"}, "options": {"label": "<Label>"}},
        )
    assert HTML(result).has("b")
    assert "&lt;Post&gt;:&lt;Label&gt;" in result


def test_render_exact_template_and_local_keywords_are_preserved(partial_app):
    with partial_app.app_context():
        result = render("exact/file.html", title="<Reader>")
        assert HTML(result).has("i")
        assert "&lt;Reader&gt;" in result
        with pytest.raises(TemplateNotFound):
            render("exact/file")


def test_render_explicit_locals_override_inferred_record(partial_app, post):
    with partial_app.app_context():
        result = render(post, locals={"post": Post(2, "Override")})
    assert HTML(result).text == "Override"


def test_render_rejects_ambiguous_template_and_partial(partial_app):
    with partial_app.app_context(), pytest.raises(ValueError, match="not both"):
        render("exact/file.html", partial="posts/post")


@pytest.mark.parametrize("source", ["target", "content", "partial", "partial_record"])
def test_stream_rendering_infers_record_partials_or_uses_explicit_locals(
    partial_app, post, source
):
    with partial_app.app_context():
        if source == "target":
            result = turbo_stream.replace(post)
        elif source == "content":
            result = turbo_stream.append("posts", post)
        elif source == "partial_record":
            result = turbo_stream.append("posts", partial=post)
        else:
            result = turbo_stream.append(
                "posts", partial="posts/post", locals={"post": post}
            )
    html = HTML(result)
    assert html.has("turbo-stream", target="post_1" if source == "target" else "posts")
    assert html.has("template")
    assert html.has("article", id="post_1")


def test_stream_explicit_text_overrides_target_record_inference(partial_app, post):
    with partial_app.app_context():
        result = turbo_stream.update(post, "<Plain text>")
    assert "&lt;Plain text&gt;" in result
    assert not HTML(result).has("article")


def test_stream_partial_rendering_preserves_dict_locals(partial_app):
    with partial_app.app_context():
        result = turbo_stream.update_all(
            ".post",
            partial="posts/details",
            locals={"item": {"title": "<Post>"}, "options": {"label": "Summary"}},
        )
    assert HTML(result).has("b")
    assert "&lt;Post&gt;:Summary" in result


def test_jinja_stream_and_nested_partial_share_render_local_helper_state(
    view_app_factory,
):
    app = view_app_factory()
    app.jinja_loader = DictLoader(
        {
            "probe.html": (
                "{{ next_number() }}|"
                "{{ turbo_stream.update('post', partial='posts/counter') }}|"
                "{{ next_number() }}"
            ),
            "posts/_counter.html": "{{ next_number() }}|{{ render(partial='posts/inner') }}",
            "posts/_inner.html": "{{ next_number() }}|{{ title }}|{{ caption() }}",
        }
    )
    client = app.test_client()
    for _ in range(2):
        response = client.get("/", headers={"X-Title": "<Posts>"})
        assert HTML(response.text).text == "1|2|3|<Posts>|<Posts>|4"
        assert "&lt;Posts&gt;" in response.text


def test_application_helpers_render_and_stream_through_the_same_view(view_app_factory):
    class PartialHelper:
        def post_body(self):
            return self.render(partial="posts/body", locals={"label": "Reader"})

        def post_stream(self):
            return self.turbo_stream.update(
                "post", partial="posts/body", locals={"label": "Stream"}
            )

    class CustomController(PostsController):
        helper(PartialHelper)

    init(CustomController)
    app = view_app_factory(include_all=False)
    app.jinja_loader = DictLoader(
        {
            "probe.html": "{{ next_number() }}|{{ post_body() }}|{{ post_stream() }}|{{ next_number() }}",
            "posts/_body.html": "<b>{{ next_number() }}:{{ label }}:{{ caption() }}:{{ title }}:{{ viewer() }}</b>",
        }
    )
    app.add_url_rule("/custom", view_func=lambda: CustomController().show())
    client = app.test_client()
    for _ in range(2):
        result = client.get("/custom", headers={"X-Viewer": "member"}).text
        assert (
            HTML(result).text
            == "1|2:Reader:Posts:Posts:member|3:Stream:Posts:Posts:member|4"
        )
        assert HTML(result).has("turbo-stream", action="update", target="post")


def test_python_stream_rendering_retains_controller_assigns(view_app_factory):
    app = view_app_factory()
    app.jinja_loader = DictLoader({"posts/_body.html": "{{ title }}|{{ caption() }}"})
    with app.test_request_context("/"):
        controller = PostsController()
        controller.title = "Assigned"
        result = turbo_stream.update("post", partial="posts/body")
    assert HTML(result).text == "Assigned|Assigned"


def test_stream_partial_failures_restore_helper_state(view_app_factory):
    app = view_app_factory()
    app.jinja_loader = DictLoader(
        {
            "probe.html": "{{ next_number() }}{{ turbo_stream.update('post', partial='missing') }}"
        }
    )
    with app.app_context():
        with pytest.raises(TemplateNotFound):
            render_template("probe.html")
        assert render_template_string("{{ next_number() }}") == "1"


def test_stream_helper_state_is_isolated_between_applications(view_app_factory):
    first = view_app_factory()
    second = view_app_factory(include_all=False)
    templates = {
        "probe.html": "{{ next_number() }}|{{ turbo_stream.update('post', partial='counter') }}",
        "_counter.html": "{{ next_number() }}|{{ post_link is defined }}",
    }
    first.jinja_loader = DictLoader(templates)
    second.jinja_loader = DictLoader(templates)
    with first.app_context():
        assert HTML(render_template("probe.html")).text == "1|2|True"
        with second.app_context():
            assert HTML(render_template("probe.html")).text == "1|2|False"
        assert HTML(render_template("probe.html")).text == "1|2|True"
