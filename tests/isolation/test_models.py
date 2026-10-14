from io import BytesIO
from types import SimpleNamespace

import pytest
from flask import Flask
from itsdangerous import BadSignature
from sqlalchemy import text
from sqlalchemy.exc import ArgumentError, NoReferencedColumnError, OperationalError

from flaskteroids.application import Application
from flaskteroids.db import session
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.extensions.db import SQLAlchemyExtension
from flaskteroids.model import Model, before_save, belongs_to, has_many, init
from flaskteroids.rules import rules
from tests.isolation.models.records import Author, Story


@pytest.mark.parametrize("order", [("a", "b"), ("b", "a")])
def test_shared_models_bind_to_independent_databases(make_app, order):
    apps = {name: make_app(name) for name in order}
    for name in ("a", "b", "a"):
        with apps[name].app_context():
            author = Author.find_by(name=name)
            if author is None:
                author = Author.create(name=name, passcode="secret")
                editor = Author.create(name=f"{name}-editor", passcode="secret")
                story = Story.create(title=name, author=author, editor=editor)
                assert story.author.name == name
                assert story.editor.name == f"{name}-editor"
                assert len(author.stories) == 1
                assert len(editor.edited_stories) == 1
                author.stories.create(title="second", editor=editor)
            assert Author.where(Author.name == name).count() == 1
            assert Story.count() == 2
            loaded = Author.includes("stories").where(name=name).first()
            assert loaded.stories.create(
                title="extra", editor=Author.find_by(name=f"{name}-editor")
            ).id
            assert Story.find_by(title="second").editor.name == f"{name}-editor"
            assert author.update(name=name)
            assert author.__json__()["name"] == name
            assert "passcode_digest" not in author.__json__()
            assert Author.authenticate_by(name=name, passcode="secret").id == author.id
            assert Story.new(author_id=999, editor_id=999).save() is False
            invalid = Story.new(author_id=999, editor_id=999)
            assert invalid.save() is False
            assert len(invalid.errors) == 2
            assert Story.where(title="extra").first().destroy()
    with apps["a"].app_context():
        Author.find_by(name="a").destroy()
        assert Story.count() == 0
    with apps["b"].app_context():
        assert Story.count() == 2


def test_building_app_b_inside_a_does_not_change_a(make_app):
    app_a = make_app("a")
    with app_a.app_context():
        author = Author.create(name="a", passcode="secret")
        session.commit()
        app_b = make_app("b")
        assert Author.find(author.id).name == "a"
        with app_b.app_context():
            assert Author.count() == 0
            Author.create(name="b", passcode="secret")
        assert Author.find(author.id).name == "a"


@pytest.mark.parametrize("tables", [(), ("authors",), ("stories",)])
def test_incomplete_schema_never_uses_another_apps_mapping(make_app, tables):
    app_a = make_app("a")
    with app_a.app_context():
        Author.create(name="a", passcode="secret")
        session.commit()
        app_b = make_app("b", tables=tables)
        with app_b.app_context():
            if "stories" in tables:
                assert Story.count() == 0
                with pytest.raises(ProgrammerError, match="Author.*migrations"):
                    Story.includes("author").first()
                with pytest.raises(ProgrammerError, match="Author.*migrations"):
                    Story.new(title="b", author_id=1, editor_id=1).save()
            else:
                with pytest.raises(ProgrammerError, match="Story.*migrations"):
                    Story.count()
            if "authors" in tables:
                author = Author.create(name="b", passcode="secret")
                with pytest.raises(ProgrammerError, match="Story.*migrations"):
                    list(author.stories)
                with pytest.raises(ProgrammerError, match="Story.*migrations"):
                    Author.includes("stories").first()
            else:
                with pytest.raises(ProgrammerError, match="Author.*migrations"):
                    Author.count()
        assert Author.count() == 1


@pytest.mark.parametrize(
    "operation", ["construct", "query", "expression", "eager_load", "relation_create"]
)
def test_unbacked_model_use_identifies_expected_table_and_recovery(make_app, operation):
    with make_app("missing", tables=("authors",)).app_context():
        author = Author.create(name="available", passcode="secret")
        with pytest.raises(ProgrammerError, match="Story.*stories.*migrations.*fresh"):
            if operation == "construct":
                Story.new(title="draft")
            elif operation == "query":
                Story.count()
            elif operation == "expression":
                _ = Story.title == "draft"
            elif operation == "eager_load":
                Author.includes("stories").first()
            else:
                author.stories.create(title="draft")


def test_partial_schema_does_not_block_unrelated_assignment(make_app, mocker):
    @rules(belongs_to("author"))
    class Story(Model):
        delivery_hint = None

    mocker.patch(
        "flaskteroids.extensions.db.discover_classes",
        return_value={"Story": Story, "Author": Author},
    )
    with make_app("partial", tables=("stories",)).app_context():
        story = Story.new(title="draft", delivery_hint="preview")
        story.title = "edited"
        story.delivery_hint = "mail"
        assert story.title == "edited"
        assert story.delivery_hint == "mail"
        with pytest.raises(AttributeError, match="Story.titel"):
            story.titel = "typo"
        with pytest.raises(
            ProgrammerError, match="Author.*authors.*migrations"
        ) as raised:
            _ = story.author
        assert "Story.author" in " ".join(raised.value.__notes__)


def test_model_access_requires_an_app_context(make_app):
    for name in ("a", "b"):
        with make_app(name).app_context():
            assert Author.count() == 0
    with pytest.raises(RuntimeError, match="Working outside of application context"):
        Author.count()


def test_unregistered_model_fails_clearly(make_app):
    class Stranger(Model):
        pass

    with (
        make_app("a").app_context(),
        pytest.raises(ProgrammerError, match="Stranger.*not registered"),
    ):
        Stranger.count()


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


@pytest.mark.parametrize("tables", [(), ("authors", "stories")])
def test_unknown_association_target_is_a_configuration_error(make_app, mocker, tables):
    @rules(belongs_to("unknown"))
    class Story(Model):
        pass

    init(Story)
    mocker.patch(
        "flaskteroids.extensions.db.discover_classes", return_value={"Story": Story}
    )
    with pytest.raises(ProgrammerError, match="Unknown model not found.*Story.unknown"):
        make_app("broken", tables=tables)


def test_invalid_association_on_existing_tables_is_not_ignored(make_app, mocker):
    @rules(belongs_to("author", foreign_key="missing_id"))
    class Story(Model):
        pass

    mocker.patch(
        "flaskteroids.extensions.db.discover_classes",
        return_value={"Story": Story, "Author": Author},
    )
    with pytest.raises(ProgrammerError, match="Story.author.*missing_id"):
        make_app("broken")


def test_attachment_column_conflict_is_checked_for_each_app(make_app):
    app = make_app("a")
    with app.app_context():
        session.execute(text("ALTER TABLE authors ADD COLUMN avatar TEXT"))
    with pytest.raises(ProgrammerError, match="Attachment avatar.*column.*Author"):
        make_app("a")


def test_existing_foreign_key_targets_outside_the_model_catalog_are_reflected(
    make_app, mocker
):
    class Story(Model):
        pass

    mocker.patch(
        "flaskteroids.extensions.db.discover_classes", return_value={"Story": Story}
    )
    app = make_app("a")
    with app.app_context():
        assert Story.create(title="standalone").id
        assert Story.count() == 1


def test_invalid_foreign_key_to_an_existing_table_is_not_ignored(make_app, mocker):
    app = make_app("a")
    with (
        app.extensions["flaskteroids.db"].new_session() as db_session,
        db_session.begin(),
    ):
        db_session.execute(text("DROP TABLE stories"))
        db_session.execute(
            text(
                "CREATE TABLE stories ("
                "id INTEGER PRIMARY KEY, author_id INTEGER REFERENCES authors(missing_id))"
            )
        )

    class Story(Model):
        pass

    mocker.patch(
        "flaskteroids.extensions.db.discover_classes", return_value={"Story": Story}
    )
    with pytest.raises(NoReferencedColumnError, match="authors.*missing_id"):
        make_app("a")


def test_migrations_require_a_fresh_app_to_bind_missing_models(make_app):
    original = make_app("a", tables=("stories",))
    migrated = make_app("a")
    with migrated.app_context():
        Author.create(name="migrated", passcode="secret")
    with original.app_context():
        assert Story.count() == 0
        with pytest.raises(ProgrammerError, match="Author.*migrations"):
            Author.count()
    with migrated.app_context():
        assert Author.first().name == "migrated"


def test_existing_table_without_primary_key_is_malformed(make_app, mocker):
    app = make_app("malformed")
    with app.app_context():
        session.execute(text("DROP TABLE stories"))
        session.execute(text("CREATE TABLE stories (title TEXT)"))

    class Story(Model):
        pass

    mocker.patch(
        "flaskteroids.extensions.db.discover_classes", return_value={"Story": Story}
    )
    with pytest.raises(ProgrammerError, match="Story.*stories.*primary key"):
        make_app("malformed")


def test_association_requires_target_identity_column(make_app, mocker):
    app = make_app("identity", tables=())
    with app.app_context():
        session.execute(text("CREATE TABLE authors (key INTEGER PRIMARY KEY)"))
        session.execute(
            text("CREATE TABLE stories (id INTEGER PRIMARY KEY, author_id INTEGER)")
        )

    @rules(belongs_to("author"))
    class Story(Model):
        pass

    class Author(Model):
        pass

    mocker.patch(
        "flaskteroids.extensions.db.discover_classes",
        return_value={"Story": Story, "Author": Author},
    )
    with pytest.raises(ProgrammerError, match="Story.author.*Author.*authors.*id"):
        make_app("identity")


def test_ambiguous_inverse_names_both_models_and_foreign_key(make_app, mocker):
    @rules(
        belongs_to("author"),
        belongs_to("editor", class_name="Author", foreign_key="author_id"),
    )
    class Story(Model):
        pass

    @rules(has_many("stories"))
    class Author(Model):
        pass

    mocker.patch(
        "flaskteroids.extensions.db.discover_classes",
        return_value={"Story": Story, "Author": Author},
    )
    with pytest.raises(ProgrammerError, match="Author.stories.*Story.*author_id"):
        make_app("ambiguous")


def test_genuine_mapper_configuration_failure_has_collective_context(make_app, mocker):
    @rules(
        belongs_to("mentor", class_name="Author", foreign_key="id"),
        has_many("mentees", class_name="Author", foreign_key="id"),
    )
    class Author(Model):
        pass

    mocker.patch(
        "flaskteroids.extensions.db.discover_classes", return_value={"Author": Author}
    )
    with pytest.raises(ArgumentError) as raised:
        make_app("mapper")
    notes = " ".join(raised.value.__notes__)
    assert "Author.mentor" in notes
    assert "Author.mentees" in notes


def test_relationship_dependency_failure_is_preserved_and_not_published(
    make_app, mocker
):
    error = RuntimeError("relationship dependency failed")
    mocker.patch("flaskteroids.extensions.db.relationship", side_effect=error)
    attempted = []

    class ObservedApplication(Application):
        def __init__(self, **kwargs):
            attempted.append(self)
            super().__init__(**kwargs)

    with pytest.raises(RuntimeError) as raised:
        make_app("failure", application_class=ObservedApplication)
    assert raised.value is error
    assert "Author.stories" in " ".join(error.__notes__)
    assert "flaskteroids.db" not in attempted[0].extensions


@pytest.mark.parametrize(
    "boundary",
    [
        "sqlalchemy.engine.Engine.connect",
        "sqlalchemy.engine.reflection.Inspector.reflect_table",
    ],
)
def test_database_failures_are_not_missing_migrations(make_app, mocker, boundary):
    original = make_app("database")
    app = Flask(__name__)
    app.database_url = original.database_url
    app.config.paths = SimpleNamespace(models="tests.isolation.models")
    error = OperationalError("database unavailable", {}, None)
    mocker.patch(boundary, side_effect=error)
    with pytest.raises(OperationalError) as raised:
        SQLAlchemyExtension(app)
    assert raised.value is error
    assert "flaskteroids.db" not in app.extensions


def test_successful_database_setup_is_a_no_op_when_repeated(make_app):
    app = make_app("repeat")
    extension = app.extensions["flaskteroids.db"]
    with app.app_context():
        author = Author.create(name="kept", passcode="secret")
        extension.init_app(app)
        extension.init_models()
        assert Author.find(author.id).name == "kept"
        assert Author.count() == 1


def test_missing_model_callback_is_reported_without_a_database_context():
    @rules(before_save("_missing"))
    class Record(Model):
        pass

    with pytest.raises(ProgrammerError, match="Callback method.*_missing.*Record"):
        init(Record)
