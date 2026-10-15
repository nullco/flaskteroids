from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from flask import render_template_string
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from flaskteroids.application import Application
from flaskteroids.db import session
from flaskteroids.testing import TestDeliveryMethod, TestQueueAdapter
from flaskteroids.testing.database import transactional_test
from tests.isolation.models.records import Author, Story


@pytest.fixture
def lazy_app(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    def create(url, initializer=None):
        root = tmp_path / "lazy"
        (root / "config").mkdir(parents=True, exist_ok=True)
        (root / "config/database.yml").write_text(f'test:\n  url: "{url}"\n')
        if initializer:
            directory = root / "config/initializers"
            directory.mkdir()
            (directory / "query.py").write_text(initializer)

        class LazyApplication(Application):
            def configure(self, config):
                config.paths.models = "tests.isolation.models"
                config.paths.jobs = "tests.isolation.jobs"
                config.paths.mailers = "tests.isolation.mailers"
                config.paths.controllers = "tests.isolation.controllers"
                config.paths.routes = "tests.isolation.routes"
                config.active_job.queue_adapter = TestQueueAdapter
                config.action_mailer.delivery_method = TestDeliveryMethod

        return LazyApplication.initialize(environment="test", root_path=root)

    return create


def test_startup_catalog_sessions_shell_and_templates_do_not_connect(
    lazy_app, tmp_path, mocker
):
    connection = mocker.patch.object(
        Engine, "connect", side_effect=AssertionError("unexpected connection")
    )
    filename = tmp_path / "missing.sqlite"
    app = lazy_app(f"sqlite:///{filename}")
    db = app.extensions["flaskteroids.db"]
    with app.app_context():
        db.init_models()
        assert db.models["Author"] is Author
        assert app.make_shell_context()["Author"] is Author
        assert render_template_string("{{ Author.__name__ }}") == "Author"
        with db.new_session():
            pass
        with db.create_session():
            pass
    assert app.test_client().get("/up/").status_code == 200
    connection.assert_not_called()
    assert not filename.exists()


def test_unavailable_database_is_deferred_but_startup_queries_are_not(
    lazy_app, tmp_path
):
    url = f"sqlite:///{tmp_path / 'absent' / 'database.sqlite'}"
    app = lazy_app(url)
    with app.app_context(), pytest.raises(OperationalError):
        Author.first()


def test_initializer_queries_fail_normally(lazy_app, tmp_path):
    url = f"sqlite:///{tmp_path / 'absent' / 'database.sqlite'}"
    with pytest.raises(OperationalError):
        lazy_app(
            url, "from tests.isolation.models.records import Author\nAuthor.first()\n"
        )


def test_runtime_uses_declared_metadata_without_reflection(make_app, mocker):
    reflect = mocker.patch(
        "sqlalchemy.engine.reflection.Inspector.reflect_table",
        side_effect=AssertionError("runtime reflection"),
    )
    with make_app("declared").app_context():
        author = Author.create(name="Ada", passcode="secret")
        story = Story.create(title="First", author=author, editor=author)
        assert Author.includes("stories").find(author.id) is author
        assert story.author is author
        assert story.editor is author
        assert author.stories == [story]
    reflect.assert_not_called()


def test_startup_only_discovers_models_without_preparing_mappings(
    lazy_app, tmp_path, mocker
):
    prepare = mocker.patch(
        "flaskteroids._models.mapping.ensure_mapped",
        side_effect=AssertionError("startup must not prepare models"),
    )
    app = lazy_app(f"sqlite:///{tmp_path / 'not_created.sqlite'}")
    assert app.extensions["flaskteroids.db"].models == {
        "Author": Author,
        "Story": Story,
    }
    prepare.assert_not_called()
    assert not (tmp_path / "not_created.sqlite").exists()


def test_database_schema_changes_do_not_mutate_published_mappings(make_app):
    with make_app("stable").app_context():
        mapper = inspect(Author.prepare())
        assert "extra" not in mapper.columns
        session.execute(text("ALTER TABLE authors ADD COLUMN extra TEXT"))
        author = Author.create(name="Ada", passcode="secret")
        assert "extra" not in author.column_names
        assert inspect(Author) is mapper


def test_concurrent_sessions_share_classes_not_identity_maps(make_app):
    app = make_app("concurrent")
    barrier = Barrier(4)

    def query(_):
        with app.app_context():
            barrier.wait(timeout=10)
            assert Author.count() == 0
            assert Author.includes("stories").all() == []
            return inspect(Author)

    with ThreadPoolExecutor(max_workers=4) as pool:
        mappers = list(pool.map(query, range(4)))
    assert all(mapper is inspect(Author) for mapper in mappers)
    assert len(list(Author.registry.mappers)) == 2


def test_transactional_tests_rollback_facade_and_native_relationship_writes(make_app):
    app = make_app("transactions")
    with transactional_test(app), app.app_context():
        author = Author.create(name="rolled back", passcode="secret")
        child = Story.create(title="temporary", author=author, editor=author)
        session.commit()
        assert Story.find(child.id).author is author
        assert Author.includes("stories").first().stories == [child]
    with app.app_context():
        assert Author.count() == Story.count() == 0
