from io import BytesIO

import pytest

from flaskteroids.app import finalize_app, initialize_app
from flaskteroids.attachments.extension import AttachmentsExtension
from flaskteroids.db import session
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.extensions.db import SQLAlchemyExtension
from flaskteroids.extensions.jobs import JobsExtension
from flaskteroids.extensions.mail import MailExtension
from flaskteroids.extensions.routes import RoutesExtension
from tests.isolation.models.records import Author


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


def test_shell_context_does_not_mutate_models_or_commit_pending_uploads(make_app):
    a, b = make_app("a"), make_app("b")
    with a.app_context():
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
        author = Author.first()
        assert author.update(name="updated")
        assert a.config["EVENTS"] == [("commit", "a")]
        session.rollback()
    assert a.config["EVENTS"] == [("commit", "a"), ("rollback", "updated")]


@pytest.mark.parametrize("key", ["db", "jobs", "mail", "routes", "attachments"])
def test_resource_owning_extensions_cannot_be_rebound(make_app, key):
    a, b = make_app("a"), make_app("b")
    with pytest.raises(ProgrammerError, match="cannot be shared"):
        a.extensions[f"flaskteroids.{key}"].init_app(b)
    assert a.test_client().get("/counter/").data == b"a"
    assert b.test_client().get("/counter/").data == b"b"
