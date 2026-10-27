import pytest
from flask import Flask

from flaskteroids.controller import Controller, init


@pytest.fixture(autouse=True)
def render_template(mocker):
    return mocker.patch("flaskteroids.controller.render_template")


@pytest.fixture(scope="module")
def response_client():
    controllers = []

    def build(action):
        class ResponsesController(Controller):
            def show(self):
                return action(self)

        init(ResponsesController)
        controllers.append(ResponsesController)
        app = Flask(__name__)
        app.testing = True

        def view():
            return ResponsesController().show()

        app.add_url_rule("/response/", endpoint="response", view_func=view)
        app.add_url_rule(
            "/response.json",
            endpoint="response_json",
            view_func=view,
            strict_slashes=False,
        )
        app.add_url_rule(
            "/response.turbo_stream",
            endpoint="response_turbo_stream",
            view_func=view,
            strict_slashes=False,
        )
        return app.test_client()

    return build
