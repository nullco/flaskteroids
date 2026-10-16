from functools import wraps
from io import BytesIO

import pytest
from flask import current_app, render_template
from jinja2 import DictLoader

from flaskteroids.app import finalize_app, initialize_app
from flaskteroids.application import Application
from flaskteroids.attachments.extension import AttachmentsExtension
from flaskteroids.db import session
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.extensions.db import SQLAlchemyExtension
from flaskteroids.extensions.jobs import JobsExtension
from flaskteroids.extensions.mail import MailExtension
from flaskteroids.extensions.routes import RoutesExtension
from flaskteroids.flash import flash
from flaskteroids.jobs.job import Job
from tests.isolation.models.records import Author


class BootstrapJob(Job):
    def perform(self):
        current_app.config["EVENTS"].append(("bootstrap", current_app.config["OWNER"]))


class RecordingApplication(Application):
    def before_request(self, fn):
        @wraps(fn)
        def callback():
            self.config.setdefault("SETUP_EVENTS", []).append("request")
            return fn()

        return super().before_request(callback)

    def context_processor(self, fn):
        @wraps(fn)
        def callback():
            self.config.setdefault("SETUP_EVENTS", []).append("template")
            return fn()

        return super().context_processor(callback)

    def shell_context_processor(self, fn):
        @wraps(fn)
        def callback():
            self.config.setdefault("SETUP_EVENTS", []).append("shell")
            return fn()

        return super().shell_context_processor(callback)


def test_initializers_register_jobs_in_the_app_being_built(make_app, tmp_path):
    for name in ("a", "b"):
        directory = tmp_path / name / "config" / "initializers"
        directory.mkdir(parents=True)
        (directory / "jobs.py").write_text(
            "from flask import current_app\n"
            "from tests.isolation.models.records import Author\n"
            "from tests.isolation.test_setup import BootstrapJob\n"
            'assert current_app.extensions["flaskteroids.db"].models["Author"] is Author\n'
            'current_app.extensions["flaskteroids.jobs"].register_job("bootstrap", BootstrapJob)\n'
            "BootstrapJob().perform_later()\n"
        )
    a = make_app("a")
    with a.app_context():
        b = make_app("b")
    for app in (a, b):
        initialize_app(app)
        finalize_app(app)
    with b.app_context():
        a.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
    b.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
    assert a.config["EVENTS"] == [("bootstrap", "a")]
    assert b.config["EVENTS"] == [("bootstrap", "b")]


def test_complete_setup_and_extension_setup_are_repeatable(make_app):
    app = make_app("a")
    routes = list(app.url_map.iter_rules())
    for _ in range(2):
        initialize_app(app)
        finalize_app(app)
        for extension in (
            SQLAlchemyExtension,
            JobsExtension,
            MailExtension,
            RoutesExtension,
            AttachmentsExtension,
        ):
            extension(app)
    assert list(app.url_map.iter_rules()) == routes
    assert app.test_client().get("/counter/").data == b"a"
    assert app.config["EVENTS"] == ["before", "action"]
    assert app.test_client().get("/up/").status_code == 200
    assert app.test_client().get("/").status_code == 200
    with app.app_context():
        Author.create(name="a", passcode="secret")
    assert app.config["EVENTS"][-1:] == [("commit", "a")]


def test_repeated_setup_runs_middleware_processors_and_csrf_once(make_app):
    app = make_app("a", application_class=RecordingApplication)
    app.config.action_controller.allow_forgery_protection = True
    app.jinja_loader = DictLoader(
        {
            "setup.html": (
                "{{ csrf_token() }}|{{ flash.notice }}|{{ Author.__name__ }}|"
                "{{ request.remote_addr }}|"
                '{{ request.environ["werkzeug.proxy_fix.orig"]["REMOTE_ADDR"] }}'
            )
        }
    )

    @app.route("/setup/", methods=["GET", "POST"])
    def setup():
        flash["notice"] = "hello"
        return render_template("setup.html")

    for _ in range(2):
        initialize_app(app)
        finalize_app(app)
    with app.app_context():
        assert app.make_shell_context()["Author"] is Author
    assert app.config["SETUP_EVENTS"] == ["shell"]
    app.config["SETUP_EVENTS"].clear()
    client = app.test_client()
    response = client.get("/setup/", headers={"X-Forwarded-For": "198.51.100.7"})
    token, notice, model, address, original_address = response.text.split("|")
    assert (notice, model, address, original_address) == (
        "hello",
        "Author",
        "198.51.100.7",
        "127.0.0.1",
    )
    assert app.config["SETUP_EVENTS"] == ["request", "template"]
    app.config["SETUP_EVENTS"].clear()
    assert client.post("/setup/", data={"csrf_token": token}).status_code == 200
    assert app.config["SETUP_EVENTS"] == ["request", "template"]
    app.config["SETUP_EVENTS"].clear()
    assert client.post("/setup/").status_code == 400
    assert app.config["SETUP_EVENTS"] == ["request"]


def test_shell_context_preserves_models_and_pending_uploads(make_app):
    a, b = make_app("a"), make_app("b")
    with a.app_context():
        session.begin()
        shell = a.make_shell_context()
        assert shell["Author"] is Author
        a.make_shell_context()
        author = shell["Author"].create(name="a", passcode="secret")
        author.avatar.attach(io=BytesIO(b"pending"), filename="file.txt")
        a.make_shell_context()
        assert a.config["EVENTS"] == []
        with b.app_context():
            assert b.make_shell_context()["Author"] is Author
            assert Author.count() == 0
        assert a.config["EVENTS"] == []
        shell["session"].commit()
        assert a.config["EVENTS"] == [("commit", "a")]
        assert author.avatar.download() == b"pending"
    assert a.config["EVENTS"] == [("commit", "a")]
    with a.app_context():
        session.begin()
        author = Author.first()
        assert author.update(name="updated")
        assert a.config["EVENTS"] == [("commit", "a")]
        session.rollback()
    assert a.config["EVENTS"] == [("commit", "a"), ("rollback", "updated")]

    @a.post("/after-shell/")
    def create_author():
        Author.create(name="request", passcode="secret")
        return {"committed": ("commit", "request") in a.config["EVENTS"]}

    with a.app_context():
        response = a.test_client().post("/after-shell/")
        assert response.json == {"committed": True}
        assert a.config["EVENTS"] == [
            ("commit", "a"),
            ("rollback", "updated"),
            ("commit", "request"),
        ]
    assert a.config["EVENTS"] == [
        ("commit", "a"),
        ("rollback", "updated"),
        ("commit", "request"),
    ]


@pytest.mark.parametrize("key", ["db", "jobs", "mail", "routes", "attachments"])
def test_resource_owning_extensions_reject_rebinding(make_app, key):
    a, b = make_app("a"), make_app("b")
    with pytest.raises(ProgrammerError, match="cannot be shared"):
        a.extensions[f"flaskteroids.{key}"].init_app(b)
    assert a.test_client().get("/counter/").data == b"a"
    assert b.test_client().get("/counter/").data == b"b"
