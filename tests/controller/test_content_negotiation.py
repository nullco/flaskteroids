import pytest
from flask import Flask

from flaskteroids.actions import after_action, before_action
from flaskteroids.controller import ActionController, init
from flaskteroids.exceptions import DoubleRenderError, ProgrammerError


@pytest.mark.parametrize(
    "path,accept,selected",
    [
        ("/response/", None, "html"),
        ("/response/", "text/html", "html"),
        ("/response/", "application/json", "json"),
        ("/response/", "text/html;q=0.4, application/json;q=0.9", "json"),
        ("/response/", "text/html;q=0.9, application/json;q=0.4", "html"),
        ("/response/", "text/*", "html"),
        ("/response/", "application/*", "json"),
        ("/response/", "*/*", "html"),
        ("/response/", "text/html;q=0, application/json", "json"),
        ("/response.json", "text/html", "json"),
        ("/response.json/", "application/xml", "json"),
    ],
)
def test_respond_to_selects_one_handler_and_records_its_rendered_response(
    response_client, render_template, path, accept, selected
):
    events = []
    render_template.return_value = "HTML response"

    def action(controller):
        def html():
            events.append("html")
            controller.render("show")

        def json():
            events.append("json")
            controller.render(json={"format": "json"})

        controller.respond_to(html=html, json=json)
        events.append("continued")

    response = response_client(action).get(
        path, headers={"Accept": accept} if accept else {}
    )
    assert response.status_code == 200
    assert events == [selected, "continued"]
    if selected == "json":
        assert response.get_json() == {"format": "json"}
        render_template.assert_not_called()
    else:
        assert response.mimetype == "text/html"
        assert response.text == "HTML response"
        render_template.assert_called_once()


def test_respond_to_negotiates_among_the_offered_formats(response_client):
    response = response_client(
        lambda controller: controller.respond_to(
            json=lambda: controller.render(json=[])
        )
    ).get("/response/", headers={"Accept": "text/html, application/json;q=0.5"})
    assert response.status_code == 200
    assert response.get_json() == []


@pytest.mark.parametrize(
    "path,accept,offered",
    [
        ("/response/", "application/xml", ("html", "json")),
        ("/response/", "text/html;q=0, application/json;q=0", ("html", "json")),
        ("/response/", "*/*;q=0", ("html", "json")),
        ("/response/", "application/json", ("html",)),
        ("/response/", None, ("json",)),
        ("/response.json", "text/html", ("html",)),
        ("/response/", "*/*", ()),
    ],
)
def test_respond_to_records_an_unsupported_format_without_implicit_rendering(
    response_client, render_template, path, accept, offered
):
    events = []

    def handler():
        events.append("handler")
        return "Unexpected response"

    def action(controller):
        controller.respond_to(**dict.fromkeys(offered, handler))
        events.append(controller.response.status_code)

    response = response_client(action).get(
        path, headers={"Accept": accept} if accept else {}
    )
    assert response.status_code == 406
    assert events == [406]
    render_template.assert_not_called()


@pytest.mark.parametrize(
    "format_,returned,status",
    [("html", "", 200), ("json", {}, 200), ("json", [], 200), ("html", ("", 204), 204)],
)
def test_respond_to_records_native_response_values_without_an_action_return(
    response_client, render_template, format_, returned, status
):
    def action(controller):
        controller.respond_to(**{format_: lambda: returned})
        assert controller.response.status_code == status

    mime = "text/html" if format_ == "html" else "application/json"
    response = response_client(action).get("/response/", headers={"Accept": mime})
    assert response.status_code == status
    if format_ == "json":
        assert response.get_json() == returned
    else:
        assert response.data == b""
    render_template.assert_not_called()


def test_respond_to_records_redirects_without_an_action_return(response_client):
    def action(controller):
        controller.respond_to(
            html=lambda: controller.redirect_to("/destination", status=303)
        )

    response = response_client(action).get("/response/")
    assert response.status_code == 303
    assert response.headers["Location"] == "/destination"


def test_html_handlers_can_leave_template_rendering_implicit(
    response_client, render_template
):
    render_template.return_value = "Default HTML"
    response = response_client(
        lambda controller: controller.respond_to(html=lambda: None)
    ).get("/response/")
    assert response.text == "Default HTML"
    render_template.assert_called_once()


def test_json_handlers_require_an_explicit_response(response_client, render_template):
    client = response_client(
        lambda controller: controller.respond_to(json=lambda: None)
    )
    with pytest.raises(ProgrammerError):
        client.get("/response.json")
    render_template.assert_not_called()


@pytest.mark.parametrize("handler", [False, "body"])
def test_respond_to_rejects_noncallable_handlers(response_client, handler):
    client = response_client(lambda controller: controller.respond_to(html=handler))
    with pytest.raises(ProgrammerError):
        client.get("/response/")


@pytest.mark.parametrize(
    "first,second",
    [
        ("render", "respond"),
        ("respond", "respond"),
        ("respond", "render"),
        ("unsupported", "render"),
    ],
)
def test_respond_to_preserves_the_single_response_contract(
    response_client, first, second
):
    def action(controller):
        if first == "render":
            controller.render(json={})
        elif first == "respond":
            controller.respond_to(html=lambda: "First response")
        else:
            controller.respond_to(json=lambda: {})
        if second == "respond":
            controller.respond_to(html=lambda: "Second response")
        else:
            controller.render(json={})

    with pytest.raises(DoubleRenderError):
        response_client(action).get("/response/")


@pytest.mark.parametrize(
    "accept,status", [("text/html", 200), ("application/xml", 406)]
)
def test_respond_to_in_a_before_callback_halts_the_action_without_returning(
    render_template, accept, status
):
    events = []

    class NegotiatedController(ActionController):
        before_action("_negotiate")
        after_action("_after")

        def _negotiate(self):
            events.append("before")
            self.respond_to(html=lambda: "From before")

        def show(self):
            events.append("action")

        def _after(self):
            events.append("after")

    init(NegotiatedController)
    app = Flask(__name__)
    app.testing = True
    app.add_url_rule("/negotiated", view_func=lambda: NegotiatedController().show())
    response = app.test_client().get("/negotiated", headers={"Accept": accept})
    assert response.status_code == status
    assert events == ["before"]
    render_template.assert_not_called()
