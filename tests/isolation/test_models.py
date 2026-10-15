from io import BytesIO
from types import SimpleNamespace

import pytest
from flask import Flask
from itsdangerous import BadSignature
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

from flaskteroids.db import session
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.extensions.db import SQLAlchemyExtension
from tests.isolation.models.records import Author, Story


@pytest.mark.parametrize("order", [("a", "b"), ("b", "a")])
def test_shared_models_use_independent_databases_and_identity_maps(make_app, order):
    apps = {name: make_app(name) for name in order}
    for name in ("a", "b", "a"):
        with apps[name].app_context():
            author = Author.find_by(name=name)
            if author is None:
                author = Author.create(name=name, passcode="secret")
                editor = Author.create(name=f"{name}-editor", passcode="secret")
                story = Story.create(title=name, author=author, editor=editor)
                assert story.author is author
                assert story.editor is editor
                assert author.stories == [story]
                assert editor.edited_stories == [story]
                Story.create(title="second", author=author, editor=editor)
            assert Author.where(Author.name == name).count() == 1
            assert Story.count() == 2
            loaded = Author.includes("stories").where(name=name).first()
            assert loaded is author
            extra = Story.create(title="extra", author=loaded)
            assert extra.id
            assert Story.find_by(title="second").editor.name == f"{name}-editor"
            assert author.update(name=name)
            assert author.__json__()["name"] == name
            assert "passcode_digest" not in author.__json__()
            assert Author.authenticate_by(name=name, passcode="secret") is author
            assert extra.destroy()
    with apps["a"].app_context():
        assert Author.find_by(name="a").destroy()
        assert Story.count() == 0
    with apps["b"].app_context():
        assert Story.count() == 2


def test_building_app_b_inside_a_does_not_change_a(make_app):
    app_a = make_app("a")
    with app_a.app_context():
        author = Author.create(name="a", passcode="secret")
        session.commit()
        app_b = make_app("b")
        assert Author.find(author.id) is author
        with app_b.app_context():
            assert Author.count() == 0
            Author.create(name="b", passcode="secret")
        assert Author.find(author.id) is author


@pytest.mark.parametrize("tables", [(), ("authors",), ("stories",)])
def test_incomplete_database_does_not_use_another_apps_engine(make_app, tables):
    app_a = make_app("a")
    app_b = make_app("b", tables=tables)
    with app_a.app_context():
        author = Author.create(name="a", passcode="secret")
        session.commit()
        with app_b.app_context():
            missing = Story if "stories" not in tables else Author
            with pytest.raises(OperationalError):
                missing.first()
            session.rollback()
            if "authors" in tables:
                assert Author.count() == 0
        assert Author.find(author.id) is author
        assert author.name == "a"


def test_model_construction_and_expressions_need_neither_database_nor_context():
    story = Story(title="draft")
    story.title = "edited"
    assert story.title == "edited"
    assert story.changes == {"title": "edited"}
    assert inspect(story).transient
    assert str(Story.title == "edited") == "stories.title = :title_1"


def test_model_queries_require_app_context(make_app):
    with make_app("a").app_context():
        assert Author.count() == 0
    with pytest.raises(RuntimeError, match="Working outside of application context"):
        Author.count()


def test_unregistered_model_fails_clearly(make_app, discovery_package):
    import importlib

    package = discovery_package(
        {
            "__init__.py": "",
            "schema.py": (
                "import sqlalchemy as sa\n"
                "from flaskteroids.schema import Snapshot\n"
                "snapshot = Snapshot()\n"
                "metadata = snapshot.metadata\n"
                "snapshot.create_table('strangers', sa.Column('id', sa.Integer(), primary_key=True))\n"
            ),
            "models/__init__.py": (
                "from flaskteroids.model import Model\n"
                "class ApplicationModel(Model):\n    __abstract__ = True\n"
                "class Stranger(ApplicationModel): pass\n"
            ),
        }
    )
    stranger = importlib.import_module(f"{package}.models").Stranger
    with make_app("a").app_context():
        with pytest.raises(ProgrammerError, match="Stranger.*not registered"):
            stranger.count()
        with pytest.raises(ProgrammerError, match="Stranger.*not registered"):
            stranger().save()


def test_attachment_and_password_tokens_are_app_owned(make_app):
    apps = [make_app("a"), make_app("b")]
    tokens = []
    for app in apps:
        with app.app_context():
            author = Author.create(name=app.config["OWNER"], passcode="secret")
            author.avatar.attach(
                io=BytesIO(app.config["OWNER"].encode()), filename="avatar.txt"
            )
            session.commit()
            tokens.append((author.passcode_reset_token, author.avatar.blob.signed_id()))
            assert author.avatar.download() == app.config["OWNER"].encode()
    for app, other in zip(apps, reversed(tokens), strict=True):
        with app.app_context():
            author = Author.first()
            assert author.avatar.download() == app.config["OWNER"].encode()
            with pytest.raises(BadSignature):
                Author.find_by_password_reset_token(other[0])
            from flaskteroids.attachments import Blob

            assert Blob.find_signed(other[1]) is None


def test_database_constraints_remain_authoritative(make_app):
    with make_app("constraints").app_context():
        story = Story(title="invalid", author_id=999)
        with pytest.raises(IntegrityError):
            story.save()
        session.rollback()
        assert Story.count() == 0


def test_unrelated_live_columns_do_not_change_explicit_model_schema(make_app):
    app = make_app("extra_column")
    with app.app_context():
        session.execute(text("ALTER TABLE authors ADD COLUMN extra_column TEXT"))
        author = Author.create(name="kept", passcode="secret")
        assert "extra_column" not in author.column_names
        assert Author.find(author.id) is author


def test_same_mappings_work_after_migrations_without_runtime_reflection(make_app):
    original = make_app("migrated", tables=("stories",))
    before = inspect(Author)
    migrated = make_app("migrated")
    with migrated.app_context():
        Author.create(name="migrated", passcode="secret")
    with original.app_context():
        assert Author.first().name == "migrated"
        assert Story.count() == 0
        assert inspect(Author) is before


def test_database_failures_propagate_without_becoming_mapping_errors(make_app, mocker):
    original = make_app("database")
    app = Flask(__name__)
    app.database_url = original.database_url
    app.config.paths = SimpleNamespace(models="tests.isolation.models")
    error = OperationalError("database unavailable", {}, None)
    mocker.patch("sqlalchemy.engine.Engine.connect", side_effect=error)
    db = SQLAlchemyExtension(app)
    with app.app_context(), pytest.raises(OperationalError) as raised:
        Author.first()
    assert raised.value is error
    assert app.extensions["flaskteroids.db"] is db


def test_repeated_database_setup_does_not_change_models_or_identity(make_app):
    app = make_app("repeat")
    extension = app.extensions["flaskteroids.db"]
    with app.app_context():
        author = Author.create(name="kept", passcode="secret")
        extension.init_app(app)
        extension.init_models()
        assert Author.find(author.id) is author
        assert extension.models["Author"] is Author
        assert extension.metadata is Author.metadata
        assert Author.count() == 1
