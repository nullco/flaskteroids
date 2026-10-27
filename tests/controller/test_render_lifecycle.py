import pytest
from flask import Flask

from flaskteroids.actions import after_action, around_action, before_action
from flaskteroids.controller import Controller, init
from flaskteroids.exceptions import DoubleRenderError


@pytest.fixture
def lifecycle_client(render_template):
    def build(
        *, mode="implicit", before_render=False, around_halt=False, after_render=False
    ):
        events = []

        def template(*args, **kwargs):
            events.append("render")
            return "Rendered body"

        render_template.side_effect = template

        class LifecycleController(Controller):
            before_action("_first")
            before_action("_second")
            around_action("_around")
            after_action("_after")

            def _first(self):
                events.append("before:first")
                if before_render:
                    self.render(json={"from": "before"}, status=401)

            def _second(self):
                events.append("before:second")

            def _around(self):
                events.append("around:before")
                if around_halt:
                    self.render(json={"from": "around"}, status=403)
                    return
                yield
                events.append("around:after")

            def show(self):
                events.append("action")
                if mode == "explicit":
                    self.render("show")
                elif mode == "native":
                    return "Native body"

            def _after(self):
                events.append("after")
                if after_render:
                    self.render(json={"from": "after"})
                self.response.headers["X-After"] = "present"

        init(LifecycleController)
        app = Flask(__name__)
        app.testing = True
        app.add_url_rule("/lifecycle", view_func=lambda: LifecycleController().show())
        return app.test_client(), events

    return build


@pytest.mark.parametrize("mode", ["implicit", "explicit"])
def test_render_precedes_around_cleanup_and_after_callbacks(lifecycle_client, mode):
    client, events = lifecycle_client(mode=mode)
    response = client.get("/lifecycle")
    assert response.text == "Rendered body"
    assert response.headers["X-After"] == "present"
    assert events == [
        "before:first",
        "before:second",
        "around:before",
        "action",
        "render",
        "around:after",
        "after",
    ]


def test_rendering_before_callback_halts_the_action_without_returning(lifecycle_client):
    client, events = lifecycle_client(before_render=True)
    response = client.get("/lifecycle")
    assert response.status_code == 401
    assert response.get_json() == {"from": "before"}
    assert events == ["before:first"]


def test_around_callback_can_render_without_yielding(lifecycle_client):
    client, events = lifecycle_client(around_halt=True)
    response = client.get("/lifecycle")
    assert response.status_code == 403
    assert response.get_json() == {"from": "around"}
    assert events == ["before:first", "before:second", "around:before"]


def test_after_callback_can_edit_a_native_returned_response(lifecycle_client):
    client, _ = lifecycle_client(mode="native")
    response = client.get("/lifecycle")
    assert response.text == "Native body"
    assert response.headers["X-After"] == "present"


def test_after_callback_rejects_replacing_an_implicit_response(lifecycle_client):
    client, _ = lifecycle_client(after_render=True)
    with pytest.raises(DoubleRenderError):
        client.get("/lifecycle")


def test_inherited_actions_render_once_after_the_child_finishes(render_template):
    class ParentController(Controller):
        def show(self):
            self.title = "Parent"

    init(ParentController)

    class ChildController(ParentController):
        def show(self):
            super().show()
            self.title = "Child"

    init(ChildController)
    render_template.side_effect = lambda template, **assigns: assigns["title"]
    app = Flask(__name__)
    app.testing = True
    app.add_url_rule("/child", view_func=lambda: ChildController().show())
    assert app.test_client().get("/child").text == "Child"
    render_template.assert_called_once()
