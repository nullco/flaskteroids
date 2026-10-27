import pytest
from flask import Flask, make_response

from flaskteroids.actions import after_action, around_action, before_action
from flaskteroids.controller import APIController, Controller, init
from flaskteroids.exceptions import DoubleRenderError, ProgrammerError


@pytest.fixture
def controller_client():
    def build(action, *, base=APIController):
        class ExamplesController(base):
            def show(self):
                return action(self)

        init(ExamplesController)
        app = Flask(__name__)
        app.testing = True
        app.add_url_rule("/", view_func=lambda: ExamplesController().show())
        return app.test_client()

    return build


def test_empty_api_action_returns_no_content(controller_client):
    response = controller_client(lambda controller: None).get("/")

    assert response.status_code == 204
    assert response.data == b""
    assert "Content-Type" not in response.headers


@pytest.mark.parametrize("base", [APIController, Controller])
@pytest.mark.parametrize("value", [None, False, 0, "", [], {}])
def test_controller_families_render_explicit_json(controller_client, base, value):
    response = controller_client(
        lambda controller: controller.render(json=value), base=base
    ).get("/", headers={"Accept": "text/html"})

    assert response.status_code == 200
    assert response.get_json() == value
    assert response.is_json


@pytest.mark.parametrize("base", [APIController, Controller])
def test_json_render_sets_location_and_status(controller_client, base):
    response = controller_client(
        lambda controller: controller.render(
            json={"id": 1}, status=201, location="/examples/1"
        ),
        base=base,
    ).get("/")

    assert response.status_code == 201
    assert response.headers["Location"] == "/examples/1"


@pytest.mark.parametrize("base", [APIController, Controller])
def test_controller_families_enforce_one_response(controller_client, base):
    def action(controller):
        controller.render(json={})
        controller.head(204)

    with pytest.raises(DoubleRenderError):
        controller_client(action, base=base).get("/")


@pytest.mark.parametrize("base", [APIController, Controller])
def test_controller_families_accept_native_responses(controller_client, base):
    response = controller_client(
        lambda controller: make_response("plain text", 202, {"X-Example": "yes"}),
        base=base,
    ).get("/")

    assert response.status_code == 202
    assert response.text == "plain text"
    assert response.headers["X-Example"] == "yes"


def test_api_controller_redirects_without_browser_state(controller_client):
    response = controller_client(
        lambda controller: controller.redirect_to("/destination", status=303)
    ).get("/")

    assert response.status_code == 303
    assert response.headers["Location"] == "/destination"
    assert "Set-Cookie" not in response.headers


def test_explicit_api_render_requires_content(controller_client):
    with pytest.raises(ProgrammerError):
        controller_client(lambda controller: controller.render()).get("/")


def test_api_implicit_response_participates_in_callback_lifecycle():
    events = []

    class ParentController(APIController):
        before_action("_before")
        around_action("_around")
        after_action("_after")

        def show(self):
            events.append("parent")

        def _before(self):
            events.append("before")

        def _around(self):
            events.append("enter")
            yield
            events.append("exit")

        def _after(self):
            events.append(self.response.status_code)
            self.response.headers["X-After"] = "yes"

    class ChildController(ParentController):
        def show(self):
            super().show()
            events.append("child")

    init(ParentController)
    init(ChildController)
    app = Flask(__name__)
    app.add_url_rule("/", view_func=lambda: ChildController().show())

    response = app.test_client().get("/")

    assert response.status_code == 204
    assert response.headers["X-After"] == "yes"
    assert events == [
        "before",
        "enter",
        "before",
        "enter",
        "parent",
        "exit",
        200,
        "child",
        "exit",
        204,
    ]


def test_api_before_callback_can_halt_with_json():
    events = []

    class GuardedController(APIController):
        before_action("_authorize")
        after_action("_after")

        def show(self):
            events.append("action")

        def _authorize(self):
            self.render(json={"error": "unauthorized"}, status=401)

        def _after(self):
            events.append("after")

    init(GuardedController)
    app = Flask(__name__)
    app.add_url_rule("/", view_func=lambda: GuardedController().show())

    response = app.test_client().get("/")

    assert response.status_code == 401
    assert response.get_json() == {"error": "unauthorized"}
    assert events == []
