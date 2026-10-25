import pytest
from flask import render_template, request
from jinja2 import DictLoader

from flaskteroids.controller import ActionController, init
from tests.assertions import HTML


class FramePagesController(ActionController):
    def show(self):
        self.label = request.args.get("label", "Editor")
        self.response.set_etag("shared", weak="weak" in request.args)
        if request.args.get("custom"):
            self.layout = "layouts/custom.html"
        self.render("pages/show", status=422 if "invalid" in request.args else 200)

    def literal(self):
        self.render("pages/literal")


@pytest.fixture
def frame_app(view_app_factory):
    app = view_app_factory(owners=False)
    app.jinja_loader = DictLoader(
        {
            "layouts/application.html": (
                '<html><head><script src="/full.js"></script>'
                "{% block head %}{% endblock %}</head>"
                '<body data-layout="full">{% block body %}{% endblock %}</body></html>'
            ),
            "layouts/custom.html": (
                '<body data-layout="custom">{% block body %}{% endblock %}</body>'
            ),
            "pages/show.html": (
                "{% extends layout %}"
                '{% block head %}<meta name="page-head" content="{{ label }}">{% endblock %}'
                "{% block body %}{% call turbo_frame_tag('editor') %}"
                '<p>{{ label }}</p><span data-frame="{{ turbo_frame_request() }}" '
                "data-frame-id=\"{{ turbo_frame_request_id() or '' }}\"></span>"
                "{% endcall %}{% endblock %}"
            ),
            "pages/literal.html": (
                "{% extends 'layouts/application.html' %}"
                "{% block body %}<turbo-frame id='editor'>Literal</turbo-frame>{% endblock %}"
            ),
        }
    )
    init(FramePagesController)
    app.add_url_rule(
        "/pages", endpoint="pages", view_func=lambda: FramePagesController().show()
    )
    app.add_url_rule(
        "/literal",
        endpoint="literal",
        view_func=lambda: FramePagesController().literal(),
    )
    return app


@pytest.mark.parametrize("invalid", [False, True])
def test_frame_requests_use_minimal_layout_and_preserve_head_content(
    frame_app, invalid
):
    response = frame_app.test_client().get(
        "/pages?label=%3CEditor%3E" + ("&invalid=1" if invalid else ""),
        headers={"Turbo-Frame": "editor"},
    )
    html = HTML(response.text)
    assert response.status_code == (422 if invalid else 200)
    assert html.has("turbo-frame", id="editor")
    assert html.has("meta", name="page-head", content="<Editor>")
    assert html.has("meta", name="csrf-token")
    assert html.has("span", **{"data-frame": "True", "data-frame-id": "editor"})
    assert not html.has("script", src="/full.js")
    assert "&lt;Editor&gt;" in response.text


def test_frame_and_page_layouts_remain_isolated_with_cached_templates(frame_app):
    client = frame_app.test_client()
    for headers, full in [({}, True), ({"Turbo-Frame": "editor"}, False), ({}, True)]:
        response = client.get("/pages", headers=headers)
        html = HTML(response.text)
        assert html.has("body", **{"data-layout": "full"}) is full
        assert html.has("span", **{"data-frame": str(not full)})


def test_explicit_layout_inheritance_keeps_full_page_frame_extraction(frame_app):
    response = frame_app.test_client().get(
        "/literal", headers={"Turbo-Frame": "editor"}
    )
    assert HTML(response.text).has("body", **{"data-layout": "full"})
    assert HTML(response.text).has("turbo-frame", id="editor")


def test_application_can_override_the_minimal_frame_layout(frame_app):
    frame_app.jinja_loader.mapping["layouts/turbo/frame.html"] = (
        '<body data-layout="custom-frame">{% block body %}{% endblock %}</body>'
    )
    response = frame_app.test_client().get("/pages", headers={"Turbo-Frame": "editor"})
    assert HTML(response.text).has("body", **{"data-layout": "custom-frame"})


def test_controller_custom_layout_applies_to_full_pages(frame_app):
    response = frame_app.test_client().get("/pages?custom=1")
    assert HTML(response.text).has("body", **{"data-layout": "custom"})


def test_frame_selection_takes_precedence_over_a_normal_custom_layout(frame_app):
    response = frame_app.test_client().get(
        "/pages?custom=1", headers={"Turbo-Frame": "editor"}
    )
    assert HTML(response.text).has("meta", name="csrf-token")
    assert not HTML(response.text).has("body", **{"data-layout": "custom"})


@pytest.mark.parametrize("weak", [False, True])
def test_frame_and_full_page_etags_have_distinct_stable_variants(frame_app, weak):
    client = frame_app.test_client()
    path = "/pages" + ("?weak=1" if weak else "")
    page = client.get(path)
    frame = client.get(path, headers={"Turbo-Frame": "editor"})
    repeated = client.get(path)
    assert page.get_etag() != frame.get_etag()
    assert page.get_etag() == repeated.get_etag()
    assert page.get_etag()[1] is weak
    assert frame.get_etag()[1] is weak
    assert {"Accept", "Turbo-Frame"} <= set(page.vary)
    assert {"Accept", "Turbo-Frame"} <= set(frame.vary)


def test_frame_header_is_available_to_controller(frame_app):
    with frame_app.test_request_context("/pages", headers={"Turbo-Frame": "editor"}):
        controller = FramePagesController()
        assert controller.turbo_frame_request
        assert controller.turbo_frame_request_id == "editor"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_blank_frame_headers_select_the_full_layout(frame_app, value):
    headers = {} if value is None else {"Turbo-Frame": value}
    response = frame_app.test_client().get("/pages", headers=headers)
    assert HTML(response.text).has("body", **{"data-layout": "full"})


def test_layout_selection_also_works_for_native_flask_rendering(frame_app):
    with frame_app.test_request_context("/", headers={"Turbo-Frame": "editor"}):
        html = HTML(render_template("pages/show.html", label="Native"))
        assert html.has("meta", name="csrf-token")
        assert html.has("turbo-frame", id="editor")
