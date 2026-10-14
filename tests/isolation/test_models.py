from io import BytesIO

import pytest
from itsdangerous import BadSignature
from sqlalchemy import text
from sqlalchemy.exc import NoReferencedColumnError

from flaskteroids.db import session
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.model import Model, before_save, belongs_to, init
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


def test_missing_model_callback_is_reported_without_a_database_context():
    @rules(before_save("_missing"))
    class Record(Model):
        pass

    with pytest.raises(ProgrammerError, match="Callback method.*_missing.*Record"):
        init(Record)
