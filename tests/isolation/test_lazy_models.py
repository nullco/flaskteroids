from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from flask import render_template_string
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.exc import OperationalError

from flaskteroids.application import Application
from flaskteroids.db import session
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.model import Model, belongs_to, has_many
from flaskteroids.rules import rules
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


@pytest.fixture
def reflected_tables(monkeypatch):
    names = []
    original = Inspector.reflect_table

    def reflect(inspector, table, *args, **kwargs):
        names.append(table.name)
        return original(inspector, table, *args, **kwargs)

    monkeypatch.setattr(Inspector, "reflect_table", reflect)
    return names


@pytest.mark.parametrize("tables", [("authors",), ("authors", "stories")])
def test_plain_source_operations_do_not_reflect_declared_targets(
    make_app, reflected_tables, tables
):
    app = make_app("isolated", tables=tables)
    if "stories" in tables:
        with app.app_context():
            session.execute(text("DROP TABLE stories"))
            session.execute(text("CREATE TABLE stories (title TEXT)"))
    assert reflected_tables == []
    with app.app_context():
        author = Author.new(name="not saved")
        assert Author.first() is None
        assert Author.count() == 0
        assert str(Author.name) == "Author.name"
        assert reflected_tables == ["authors"]
        with pytest.raises(ProgrammerError, match="Story"):
            _ = author.stories
        assert Author.count() == 0
        assert author.name == "not saved"


def test_target_reads_preserve_unresolved_foreign_keys_without_loading_source(
    make_app, reflected_tables
):
    app = make_app("target", tables=("stories",))
    with app.app_context():
        assert Story.first() is None
        assert reflected_tables == ["stories"]
        schema = app.extensions["flaskteroids.db"].binding(Story).schema
        assert {fk.target_fullname for fk in schema.foreign_keys} == {"authors.id"}
        assert all(fk.parent in schema.columns.values() for fk in schema.foreign_keys)


def test_failed_target_load_can_retry_after_migration_without_remapping_source(
    make_app,
):
    app = make_app("retry", tables=("authors",))
    with app.app_context():
        author = Author.create(name="kept", passcode="secret")
        db = app.extensions["flaskteroids.db"]
        mapped = db.binding(Author).mapped_class
        query = Author.where(name="kept")
        identity = session.get(mapped, author.id)
        with pytest.raises(ProgrammerError, match="Story.*migrations"):
            list(author.stories)
        assert query.first().id == author.id
        session.commit()
        make_app("retry")
        story = author.stories.create(title="after migration", editor=author)
        assert story.author.id == author.id
        assert db.binding(Author).mapped_class is mapped
        assert session.get(mapped, author.id) is identity
        assert query.first().id == author.id


def test_loaded_schema_is_cached_but_unused_schema_is_not_snapshotted(make_app):
    app = make_app("lifetime", tables=("authors",))
    with app.app_context():
        assert "nickname" not in Author.new().column_names
        session.execute(text("ALTER TABLE authors ADD COLUMN nickname TEXT"))
        session.commit()
        make_app("lifetime")
        assert Story.count() == 0
        assert "nickname" not in Author.new().column_names
        fresh = make_app("lifetime")
        with fresh.app_context():
            assert "nickname" in Author.new().column_names


def test_concurrent_first_use_has_one_mapping_and_one_schema_load(
    make_app, reflected_tables
):
    app = make_app("threads")
    barrier = Barrier(6)

    def query(index):
        with app.app_context():
            barrier.wait(timeout=10)
            assert Author.count() == 0
            assert list(Author.includes("stories")) == []
            return app.extensions["flaskteroids.db"].binding(Author).mapped_class

    with ThreadPoolExecutor(max_workers=6) as pool:
        mapped = list(pool.map(query, range(6)))
    assert len(set(mapped)) == 1
    assert reflected_tables.count("authors") == reflected_tables.count("stories") == 1


def test_transactional_test_with_initially_unloaded_models_and_associations(make_app):
    app = make_app("transactions")
    with transactional_test(app), app.app_context():
        author = Author.create(name="rolled back", passcode="secret")
        child = author.stories.create(title="temporary", editor=author)
        session.commit()
        assert Story.find(child.id).author.id == author.id
        assert len(Author.includes("stories").first().stories) == 1
    with app.app_context():
        assert Author.count() == Story.count() == 0


def test_never_read_dependents_are_destroyed_and_callbacks_run(make_app, mocker):
    events = []

    from flaskteroids.model import before_destroy

    @rules(has_many("stories", dependent="destroy"))
    class Author(Model):
        pass

    @rules(belongs_to("author"), before_destroy("record_destroy"))
    class Story(Model):
        def record_destroy(self):
            events.append(self.id)

    mocker.patch(
        "flaskteroids.extensions.db.discover_classes",
        return_value={"Author": Author, "Story": Story},
    )
    app = make_app("cascade")
    with app.app_context():
        session.execute(text("INSERT INTO authors (id, name) VALUES (1, 'parent')"))
        session.execute(text("INSERT INTO stories (id, author_id) VALUES (1, 1)"))
        session.commit()
        author = Author.first()
        assert author.destroy()
        assert Story.count() == Author.count() == 0
        assert events == [1]


def test_self_tree_cycles_and_inverse_reads_do_not_configure_mapper_relationships(
    make_app, mocker
):
    @rules(
        belongs_to("mentor", class_name="Author", foreign_key="mentor_id"),
        has_many(
            "mentees", class_name="Author", foreign_key="mentor_id", dependent="destroy"
        ),
    )
    class Author(Model):
        pass

    mocker.patch(
        "flaskteroids.extensions.db.discover_classes", return_value={"Author": Author}
    )
    app = make_app("tree")
    with app.app_context():
        session.execute(
            text(
                "ALTER TABLE authors ADD COLUMN mentor_id INTEGER REFERENCES authors(id)"
            )
        )
        session.commit()
        parent = Author.new(name="parent")
        assert parent.save(validate=False)
        child = Author.create(name="child", mentor=parent)
        assert child.mentor.id == parent.id
        assert [
            entry.id for entry in Author.includes("mentees").find(parent.id).mentees
        ] == [child.id]
        assert not inspect(
            app.extensions["flaskteroids.db"].binding(Author).mapped_class
        ).relationships
        assert parent.destroy()
        assert Author.count() == 0


def test_eager_loading_does_not_walk_the_targets_other_associations(
    make_app, mocker, reflected_tables
):
    @rules(has_many("stories"))
    class Author(Model):
        pass

    @rules(belongs_to("author"), belongs_to("missing"))
    class Story(Model):
        pass

    mocker.patch(
        "flaskteroids.extensions.db.discover_classes",
        return_value={"Author": Author, "Story": Story},
    )
    with make_app("graph").app_context():
        session.execute(text("INSERT INTO authors (id) VALUES (1)"))
        session.execute(text("INSERT INTO stories (id, author_id) VALUES (1, 1)"))
        session.commit()
        author = Author.includes("stories").first()
        child = next(iter(author.stories))
        assert child.author.id == author.id
        assert reflected_tables == ["authors", "stories"]
        with pytest.raises(ProgrammerError, match="Missing model not found"):
            _ = child.missing
        assert Author.first().id == author.id
        assert child.author.id == author.id


def test_row_mapping_preserves_defaults_generated_columns_and_database_constraints(
    make_app,
):
    from sqlalchemy.exc import IntegrityError

    with make_app("projection").app_context():
        session.execute(
            text("ALTER TABLE authors ADD COLUMN status TEXT DEFAULT 'active'")
        )
        session.execute(
            text(
                "ALTER TABLE authors ADD COLUMN name_length INTEGER GENERATED ALWAYS AS (length(name)) VIRTUAL"
            )
        )
        session.commit()
        author = Author.create(name="four", passcode="secret")
        assert author.status == "active"
        assert author.name_length == 4
        session.commit()
        with pytest.raises(IntegrityError):
            Story.new(title="invalid foreign key", author_id=999).save(validate=False)
        session.rollback()
        assert Author.find(author.id).name == "four"


def test_non_dependent_destruction_nullifies_without_child_save_callbacks(
    make_app, mocker
):
    from flaskteroids.model import before_save

    events = []

    @rules(has_many("stories"))
    class Author(Model):
        pass

    @rules(before_save("record_save"))
    class Story(Model):
        def record_save(self):
            events.append(self.id)

    mocker.patch(
        "flaskteroids.extensions.db.discover_classes",
        return_value={"Author": Author, "Story": Story},
    )
    with make_app("nullify").app_context():
        session.execute(text("INSERT INTO authors (id) VALUES (1)"))
        session.execute(text("INSERT INTO stories (id, author_id) VALUES (1, 1)"))
        session.commit()
        assert Author.first().destroy()
        assert Story.first().author_id is None
        assert events == []


def test_pending_association_writes_persist_new_targets_before_foreign_keys(make_app):
    with make_app("pending").app_context():
        author = Author.new(name="new target", passcode="secret")
        story = Story.new(title="new source", author=author, editor=author)
        assert story.save(validate=False)
        assert author.is_persisted()
        assert Story.find(story.id).author.id == author.id
        assert Story.find(story.id).editor.id == author.id
        assert Author.count() == 1


def test_halted_pending_target_does_not_apply_source_changes(make_app, mocker):
    from flaskteroids.model import before_save

    @rules(before_save("halt"))
    class Author(Model):
        def halt(self):
            return False

    @rules(belongs_to("author"))
    class Story(Model):
        pass

    mocker.patch(
        "flaskteroids.extensions.db.discover_classes",
        return_value={"Author": Author, "Story": Story},
    )
    with make_app("halted").app_context():
        session.execute(text("INSERT INTO authors (id) VALUES (1)"))
        session.execute(
            text("INSERT INTO stories (id, author_id, title) VALUES (1, 1, 'kept')")
        )
        session.commit()
        story = Story.first()
        story.title = "not saved"
        story.author = Author.new(name="halted")
        assert story.save(validate=False) is False
        session.commit()
        assert story.reload().title == "kept"
        assert story.author.id == 1
        assert Author.count() == 1


def test_cyclic_unsaved_writes_fail_without_recursive_saves_or_partial_rows(
    make_app, mocker
):
    @rules(belongs_to("story"))
    class Author(Model):
        pass

    @rules(belongs_to("author"))
    class Story(Model):
        pass

    mocker.patch(
        "flaskteroids.extensions.db.discover_classes",
        return_value={"Author": Author, "Story": Story},
    )
    with make_app("pending_cycle").app_context():
        session.execute(text("ALTER TABLE authors ADD COLUMN story_id INTEGER"))
        session.commit()
        author = Author.new(name="cycle")
        story = Story.new(title="cycle", author=author)
        author.story = story
        with pytest.raises(ProgrammerError, match="Cyclic unsaved association writes"):
            author.save(validate=False)
        assert Author.count() == Story.count() == 0


@pytest.mark.parametrize(
    "declaration",
    [
        belongs_to(""),
        belongs_to("author", class_name=""),
        belongs_to("author", foreign_key=""),
        has_many("stories", dependent="delete"),
    ],
)
def test_invalid_association_syntax_fails_without_database_io(declaration, mocker):
    from flaskteroids.model import init

    @rules(declaration)
    class Record(Model):
        pass

    connect = mocker.patch.object(
        Engine, "connect", side_effect=AssertionError("unexpected I/O")
    )
    with pytest.raises(ProgrammerError):
        init(Record)
    connect.assert_not_called()


def test_association_cache_obeys_fk_assignment_reload_and_rollback(make_app):
    with make_app("cache").app_context():
        first = Author.create(name="first", passcode="secret")
        second = Author.create(name="second", passcode="secret")
        story = Story.create(title="one", author=first, editor=first)
        session.commit()
        assert story.author.id == first.id
        story.author_id = second.id
        assert story.author.id == second.id
        assert story.save()
        assert len(first.stories) == 0
        assert len(second.stories) == 1
        session.rollback()
        story.reload()
        assert story.author.id == first.id
        assert len(first.stories) == 1
        assert len(second.stories) == 0
