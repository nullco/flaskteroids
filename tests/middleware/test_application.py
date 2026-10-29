from pathlib import Path
from shutil import copyfile

import pytest
from flask import Response, request
from werkzeug.middleware.proxy_fix import ProxyFix

from flaskteroids.app import finalize_app, initialize_app
from flaskteroids.middleware import MethodOverrideMiddleware
from tests.middleware.support import ConfiguredApplication, EarlyResponse, First, Second

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def make_app(tmp_path):
    applications = []

    def create(*, api_only=False, configure=None):
        class TestApplication(ConfiguredApplication):
            def configure(self, config):
                super().configure(config)
                config.api_only = api_only
                if configure:
                    configure(config)

        app = TestApplication.initialize(environment="test", root_path=tmp_path)
        applications.append(app)
        return app

    yield create
    for app in applications:
        app.extensions["flaskteroids.db"].engine.dispose()


@pytest.mark.parametrize(
    "api_only, expected",
    [(False, [ProxyFix, MethodOverrideMiddleware, First]), (True, [ProxyFix, First])],
)
def test_application_exposes_profile_specific_defaults(make_app, api_only, expected):
    app = make_app(api_only=api_only)
    assert [entry.klass for entry in app.middleware] == expected
    assert app.test_client().get("/up/").status_code == 200


def test_application_environment_and_initializer_configuration_compose(
    make_app, tmp_path
):
    environments = tmp_path / "config/environments"
    initializers = tmp_path / "config/initializers"
    environments.mkdir(parents=True)
    initializers.mkdir(parents=True)
    copyfile(FIXTURES / "environment.py", environments / "test.py")
    copyfile(FIXTURES / "initializer.py", initializers / "middleware.py")
    app = make_app()
    events = app.config["MIDDLEWARE_EVENTS"]
    assert events == [
        ("build", "initializer"),
        ("build", "environment"),
        ("build", "First"),
    ]
    events.clear()
    assert app.test_client().get("/up/").status_code == 200
    assert events == [
        ("before", "First"),
        ("before", "environment"),
        ("before", "initializer"),
        ("after", "initializer"),
        ("after", "environment"),
        ("after", "First"),
    ]


def test_configuration_can_replace_werkzeug_middleware_with_constructor_options(
    make_app,
):
    app = make_app(
        configure=lambda config: config.middleware.swap(ProxyFix, ProxyFix, x_for=2)
    )

    @app.get("/address/")
    def address():
        return {"address": request.remote_addr}

    response = app.test_client().get(
        "/address/", headers={"X-Forwarded-For": "198.51.100.7, 198.51.100.8"}
    )
    assert response.json == {"address": "198.51.100.7"}


def test_configuration_can_remove_proxy_handling(make_app):
    app = make_app(configure=lambda config: config.middleware.delete(ProxyFix))

    @app.get("/address/")
    def address():
        return {"address": request.remote_addr}

    response = app.test_client().get(
        "/address/", headers={"X-Forwarded-For": "198.51.100.7"}
    )
    assert response.json == {"address": "127.0.0.1"}


@pytest.mark.parametrize(
    "remove_override, expected", [(False, "DELETE"), (True, "POST")]
)
def test_configuration_controls_browser_method_override(
    make_app, remove_override, expected
):
    def configure(config):
        if remove_override:
            config.middleware.delete(MethodOverrideMiddleware)

    app = make_app(configure=configure)

    @app.route("/method/", methods=["POST", "DELETE"])
    def method():
        return request.method

    assert (
        app.test_client().post("/method/", data={"_method": "DELETE"}).text == expected
    )


def test_custom_middleware_can_short_circuit_before_flask_dispatch(make_app):
    app = make_app(configure=lambda config: config.middleware.unshift(EarlyResponse))
    events = app.config["MIDDLEWARE_EVENTS"]
    events.clear()
    response = app.test_client().get("/up/")
    assert response.status_code == 503
    assert response.text == "maintenance"
    assert events == []


def test_application_streams_and_closes_response_through_middleware(make_app):
    app = make_app()
    events = []

    @app.get("/stream/")
    def stream():
        def chunks():
            try:
                events.append("first")
                yield b"first"
                events.append("second")
                yield b"second"
            finally:
                events.append("close")

        return Response(chunks())

    response = app.test_client().get("/stream/", buffered=False)
    assert next(iter(response.response)) == b"first"
    assert events == ["first"]
    response.close()
    assert events == ["first", "close"]


def test_repeated_setup_builds_middleware_once(make_app):
    app = make_app()
    stack = app.middleware
    for _ in range(2):
        initialize_app(app)
        finalize_app(app)
    assert app.middleware is stack
    assert app.config["MIDDLEWARE_EVENTS"] == [("build", "First")]
    assert app.test_client().get("/up/").status_code == 200
    assert app.config["MIDDLEWARE_EVENTS"].count(("before", "First")) == 1


def test_applications_keep_independent_middleware_configuration(make_app):
    first = make_app(configure=lambda config: config.middleware.delete(First))
    second = make_app()
    assert First not in [entry.klass for entry in first.middleware]
    assert First in [entry.klass for entry in second.middleware]
    with pytest.raises(RuntimeError, match="frozen"):
        second.config.middleware.use(Second, [])
    assert first.config["MIDDLEWARE_EVENTS"] == []
    assert second.test_client().get("/up/").status_code == 200
    assert second.config["MIDDLEWARE_EVENTS"][-2:] == [
        ("before", "First"),
        ("after", "First"),
    ]


def test_middleware_command_lists_the_effective_stack(make_app):
    app = make_app(configure=lambda config: config.middleware.delete(ProxyFix))
    result = app.test_cli_runner().invoke(args=["middleware"])
    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        *(f"use {entry.name}" for entry in app.middleware),
        "run flask.app.Flask.wsgi_app",
    ]
