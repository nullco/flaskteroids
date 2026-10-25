import pytest
from flask import render_template_string
from markupsafe import Markup

from flaskteroids.turbo import TurboStreamBuilder, turbo_frame_tag, turbo_stream
from tests.assertions import HTML
from tests.turbo.fixtures.records import Post


@pytest.mark.parametrize(
    "ids,expected",
    [
        (("messages",), "messages"),
        (("users", "active", 3), "users_active_3"),
        ((Post(1),), "post_1"),
        ((Post(1), "edit"), "edit_post_1"),
        ((Post(),), "new_post"),
        ((Post(), "edit"), "edit_post"),
        ((Post,), "new_post"),
        ((Post, "edit"), "edit_post"),
    ],
)
def test_frame_identifiers_follow_record_or_compound_conventions(ids, expected):
    assert HTML(turbo_frame_tag(*ids)).has("turbo-frame", id=expected)


def test_frame_attributes_expand_data_and_preserve_boolean_rules():
    result = turbo_frame_tag(
        "posts",
        src="/posts?page=1&order=new",
        target="_top",
        loading="lazy",
        class_="panel",
        hidden=True,
        disabled=False,
        title=None,
        data={"turbo_action": "advance", "enabled": False, "ids": [1, 2]},
        aria={"busy": True},
    )
    html = HTML(result)
    assert html.has(
        "turbo-frame",
        id="posts",
        src="/posts?page=1&order=new",
        target="_top",
        loading="lazy",
        **{
            "class": "panel",
            "hidden": "hidden",
            "data-turbo-action": "advance",
            "data-enabled": "false",
            "data-ids": "[1,2]",
            "aria-busy": "true",
        },
    )
    attrs = html.elements[0][1]
    assert "disabled" not in attrs
    assert "title" not in attrs


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "data:text/html,x", " /\n/evil", "vbscript:x"]
)
def test_frames_reject_unsafe_urls_before_capturing_content(url, mocker):
    caller = mocker.Mock()
    with pytest.raises(ValueError):
        turbo_frame_tag("posts", src=Markup(url), caller=caller)
    caller.assert_not_called()


@pytest.mark.parametrize("helper", [turbo_frame_tag, turbo_stream.update])
def test_attributes_escape_markup_without_trusting_attribute_names(helper):
    value = Markup('"><img src=x onerror="bad">')
    result = helper("posts", title=value, data={"value": value})
    assert HTML(result).has(
        "turbo-frame" if helper is turbo_frame_tag else "turbo-stream"
    )
    assert "<img" not in result
    assert "&lt;img" in result
    assert 'title="&#34;' in result
    with pytest.raises(ValueError, match="attribute name"):
        helper("posts", **{'title" onmouseover': "bad"})
    with pytest.raises(ValueError, match="attribute name"):
        helper("posts", data={'bad" name': "bad"})


@pytest.mark.parametrize(
    "action", ["append", "prepend", "before", "after", "replace", "update"]
)
def test_stream_operations_escape_text_and_preserve_markup(action, post):
    build = getattr(turbo_stream, action)
    result = build(post, "<strong>Reader</strong>")
    assert HTML(result).has("turbo-stream", action=action, target="post_1")
    assert "<template>&lt;strong&gt;Reader&lt;/strong&gt;</template>" in result
    trusted = build("posts", Markup("<strong>Reader</strong>"))
    assert HTML(trusted).has("strong")
    assert HTML(trusted).has("template")


@pytest.mark.parametrize(
    "action", ["append", "prepend", "before", "after", "replace", "update", "remove"]
)
def test_selector_operations_keep_selector_text(action):
    build = getattr(turbo_stream, action + "_all")
    options = {} if action == "remove" else {"content": "Hello"}
    result = build('.posts[data-id="1"] > article', **options)
    html = HTML(result)
    assert html.has(
        "turbo-stream", action=action, targets='.posts[data-id="1"] > article'
    )
    assert "target" not in html.elements[0][1]
    assert html.has("template") == (action != "remove")


@pytest.mark.parametrize("action", ["replace", "update"])
@pytest.mark.parametrize("selector", [False, True])
def test_stream_morph_option_is_an_attribute(action, selector):
    build = getattr(turbo_stream, action + ("_all" if selector else ""))
    result = build("posts", "Body", method="morph")
    assert HTML(result).has("turbo-stream", action=action, method="morph")


def test_custom_stream_actions_support_ids_and_selectors():
    builder = TurboStreamBuilder()
    assert HTML(builder.action("highlight", Post(1), "Hello")).has(
        "turbo-stream", action="highlight", target="post_1"
    )
    assert HTML(builder.action_all("highlight", ".post", "Hello")).has(
        "turbo-stream", action="highlight", targets=".post"
    )


def test_remove_and_refresh_omit_templates_and_skip_content_inference(post):
    removed = turbo_stream.remove(post, partial="missing/partial")
    refreshed = turbo_stream.refresh(partial="missing/partial")
    assert HTML(removed).has("turbo-stream", action="remove", target="post_1")
    assert HTML(refreshed).has("turbo-stream", action="refresh")
    assert "<template>" not in removed + refreshed
    assert "target" not in HTML(refreshed).elements[0][1]


def test_refresh_reads_request_id_and_allows_override(view_app_factory):
    app = view_app_factory()
    with app.test_request_context("/", headers={"X-Turbo-Request-Id": 'req"1'}):
        assert HTML(turbo_stream.refresh()).has(
            "turbo-stream", **{"request-id": 'req"1'}
        )
        assert HTML(turbo_stream.refresh(request_id="explicit")).has(
            "turbo-stream", **{"request-id": "explicit"}
        )
        assert (
            "request-id"
            not in HTML(turbo_stream.refresh(request_id=None)).elements[0][1]
        )
    assert "request-id" not in HTML(turbo_stream.refresh()).elements[0][1]


def test_jinja_call_blocks_capture_rendered_frame_and_stream_html(
    view_app_factory, post
):
    app = view_app_factory()
    with app.app_context():
        result = render_template_string(
            "{% call turbo_frame_tag(post, 'edit', data={'turbo': false}) %}"
            "<p>{{ title }}</p>{% endcall %}"
            "{% call turbo_stream.update(post) %}<b>{{ title }}</b>{% endcall %}",
            post=post,
            title="<Reader>",
        )
    html = HTML(result)
    assert html.has("turbo-frame", id="edit_post_1", **{"data-turbo": "false"})
    assert html.has("turbo-stream", target="post_1", action="update")
    assert html.has("p") and html.has("b")
    assert "&lt;Reader&gt;" in result


def test_jinja_identifier_helpers_are_registered(view_app_factory, post):
    app = view_app_factory()
    with app.app_context():
        assert (
            render_template_string(
                "{{ dom_id(post, 'edit') }}|{{ dom_class(post, 'edit') }}", post=post
            )
            == "edit_post_1|edit_post"
        )


@pytest.mark.parametrize("helper", [turbo_frame_tag, turbo_stream.update])
@pytest.mark.parametrize("trusted", [False, True])
def test_python_capture_callbacks_escape_plain_text_and_preserve_trusted_html(
    helper, trusted
):
    content = "<strong>Captured</strong>"
    if trusted:
        content = Markup(content)
    result = helper("posts", caller=lambda: content)
    assert HTML(result).has("strong") is trusted
    assert ("&lt;strong&gt;" in result) is not trusted


def test_frame_requires_an_id_and_limits_record_prefix_arguments(post):
    with pytest.raises(ValueError, match="identifier"):
        turbo_frame_tag()
    with pytest.raises(ValueError, match="optional prefix"):
        turbo_frame_tag(post, "edit", "extra")
