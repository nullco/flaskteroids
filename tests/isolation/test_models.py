from io import BytesIO

import pytest
from itsdangerous import BadSignature
from sqlalchemy import text

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


@pytest.mark.parametrize("tables", [(), ("authors",)])
def test_incomplete_schema_never_uses_another_apps_mapping(make_app, tables):
    app_a = make_app("a")
    with app_a.app_context():
        Author.create(name="a", passcode="secret")
        session.commit()
        app_b = make_app("b", tables=tables)
        with app_b.app_context():
            with pytest.raises(ProgrammerError, match="Story.*migrations"):
                Story.count()
            if tables:
                author = Author.create(name="b", passcode="secret")
                with pytest.raises(ProgrammerError, match="Story.*migrations"):
                    list(author.stories)
                with pytest.raises(ProgrammerError, match="Story.*migrations"):
                    Author.includes("stories").first()
            else:
                with pytest.raises(ProgrammerError, match="Author.*migrations"):
                    Author.count()
        assert Author.count() == 1


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


def test_missing_model_callback_is_reported_without_a_database_context():
    @rules(before_save("_missing"))
    class Record(Model):
        pass

    with pytest.raises(ProgrammerError, match="Callback method.*_missing.*Record"):
        init(Record)
