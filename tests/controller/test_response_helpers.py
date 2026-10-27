from http.cookies import SimpleCookie

import pytest
from flask import Flask, get_flashed_messages

from flaskteroids.actions import after_action, before_action
from flaskteroids.controller import Controller, init
from flaskteroids.exceptions import DoubleRenderError, ProgrammerError


def prepare(controller, kind):
    if kind == "render":
        controller.render(json={"rendered": True})
    elif kind == "redirect":
        controller.redirect_to("/destination")
    elif kind == "head":
        controller.head(204)
    else:
        controller.respond_to(html=lambda: "Negotiated response")


@pytest.fixture
def flash_client(response_client):
    def build(action):
        client = response_client(action)
        client.application.secret_key = "test"

        @client.application.get("/flashes")
        def messages():
            return dict(get_flashed_messages(with_categories=True))

        return client

    return build


@pytest.mark.parametrize("status", [200, 201, 202, 204, 205, 304])
def test_head_prepares_an_empty_response_without_an_action_return(
    response_client, render_template, status
):
    observed = []

    def action(controller):
        controller.head(status, headers={"X-Result": "ready"})
        observed.append(controller.performed)

    response = response_client(action).get("/response/")
    assert response.status_code == status
    assert response.data == b""
    assert response.headers["X-Result"] == "ready"
    if status in (204, 205, 304):
        assert "Content-Type" not in response.headers
    assert observed == [True]
    render_template.assert_not_called()


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_prepares_location_and_status_without_an_action_return(
    response_client, render_template, status
):
    observed = []

    def action(controller):
        controller.redirect_to("/destination", status=status)
        observed.append(controller.performed)

    response = response_client(action).get("/response/")
    assert response.status_code == status
    assert response.headers["Location"] == "/destination"
    assert response.data == b""
    assert observed == [True]
    render_template.assert_not_called()


def test_redirect_carries_notice_and_alert_to_the_next_request(flash_client):
    client = flash_client(
        lambda controller: controller.redirect_to(
            "/destination", notice="Saved", alert="Check your inbox"
        )
    )
    assert client.get("/response/").status_code == 302
    assert client.get("/flashes").get_json() == {
        "notice": "Saved",
        "alert": "Check your inbox",
    }
    assert client.get("/flashes").get_json() == {}


def test_rejected_second_redirect_preserves_the_first_flash_and_destination(
    flash_client,
):
    def action(controller):
        controller.redirect_to("/first", notice="First notice")
        with pytest.raises(DoubleRenderError):
            controller.redirect_to(
                "/second", notice="Second notice", alert="Unexpected"
            )

    client = flash_client(action)
    response = client.get("/response/")
    assert response.headers["Location"] == "/first"
    assert client.get("/flashes").get_json() == {"notice": "First notice"}


def test_redirect_rejects_a_missing_destination_without_flashing(flash_client):
    def action(controller):
        with pytest.raises(ProgrammerError):
            controller.redirect_to(None, notice="Unexpected")
        assert not controller.performed
        controller.head(422)

    client = flash_client(action)
    assert client.get("/response/").status_code == 422
    assert client.get("/flashes").get_json() == {}


@pytest.mark.parametrize(
    "kind", ["implicit", "html", "json", "head", "native", "negotiated"]
)
def test_pending_response_metadata_survives_body_preparation_without_performing(
    response_client, render_template, kind
):
    render_template.return_value = "HTML body"

    def action(controller):
        assert not controller.performed
        controller.response.status_code = 201
        controller.response.headers["X-Before"] = "retained"
        controller.response.set_cookie("first", "one")
        controller.response.set_cookie("second", "two")
        assert not controller.performed
        if kind == "html":
            controller.render("show")
        elif kind == "json":
            controller.render(json={"body": True})
        elif kind == "head":
            controller.head()
        elif kind == "native":
            return "Native body"
        elif kind == "negotiated":
            controller.respond_to(html=lambda: "Negotiated body")

    response = response_client(action).get("/response/")
    assert response.status_code == 201
    assert response.headers["X-Before"] == "retained"
    cookies = SimpleCookie()
    for value in response.headers.getlist("Set-Cookie"):
        cookies.load(value)
    assert {name: cookie.value for name, cookie in cookies.items()} == {
        "first": "one",
        "second": "two",
    }
    assert bool(response.data) is (kind != "head")


@pytest.mark.usefixtures("app_ctx")
def test_pending_metadata_is_available_before_the_first_action():
    class PreparedController(Controller):
        def show(self):
            self.render(json={"ready": True})

    controller = init(PreparedController)()
    controller.response.status_code = 201
    controller.response.headers["X-Before"] = "configured"
    assert not controller.performed
    response = controller.show()
    assert response.status_code == 201
    assert response.headers["X-Before"] == "configured"
    assert controller.performed


@pytest.mark.parametrize("kind", ["render", "head", "native", "negotiated"])
def test_explicit_response_metadata_overrides_pending_values(response_client, kind):
    def action(controller):
        controller.response.status_code = 409
        controller.response.headers["X-Result"] = "pending"
        if kind == "render":
            controller.render(json={}, status=202)
        elif kind == "head":
            controller.head(202, headers={"X-Result": "explicit"})
        elif kind == "native":
            return "Native", 202, {"X-Result": "explicit"}
        else:
            controller.respond_to(
                html=lambda: ("Native", 202, {"X-Result": "explicit"})
            )

    response = response_client(action).get("/response/")
    assert response.status_code == 202
    assert response.headers["X-Result"] == (
        "pending" if kind == "render" else "explicit"
    )


@pytest.mark.parametrize(
    "first,second",
    [
        (first, second)
        for first in ("render", "redirect", "head", "negotiated")
        for second in ("render", "redirect", "head", "negotiated")
        if "redirect" in (first, second) or "head" in (first, second)
    ],
)
def test_response_helpers_reject_preparing_a_second_response(
    response_client, first, second
):
    def action(controller):
        prepare(controller, first)
        controller.response.headers["X-After"] = "metadata only"
        assert controller.performed
        prepare(controller, second)

    with pytest.raises(DoubleRenderError):
        response_client(action).get("/response/")


@pytest.mark.parametrize("kind,status", [("redirect", 302), ("head", 204)])
def test_response_helpers_halt_before_callbacks_without_an_action_return(
    render_template, kind, status
):
    events = []

    class GuardedController(Controller):
        before_action("_metadata")
        before_action("_prepare")
        before_action("_later")
        after_action("_after")

        def _metadata(self):
            events.append("metadata")
            self.response.headers["X-Before"] = "retained"
            assert not self.performed

        def _prepare(self):
            events.append("prepare")
            prepare(self, kind)

        def _later(self):
            events.append("later")

        def show(self):
            events.append("action")

        def _after(self):
            events.append("after")

    init(GuardedController)
    app = Flask(__name__)
    app.testing = True
    app.add_url_rule("/guarded", view_func=lambda: GuardedController().show())
    response = app.test_client().get("/guarded")
    assert response.status_code == status
    assert response.headers["X-Before"] == "retained"
    assert events == ["metadata", "prepare"]
    render_template.assert_not_called()
