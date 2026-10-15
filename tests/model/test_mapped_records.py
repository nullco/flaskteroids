from types import SimpleNamespace

import pytest
from flask import Flask
from sqlalchemy import event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from flaskteroids.exceptions import ProgrammerError, RecordNotFoundException
from flaskteroids.extensions.db import SQLAlchemyExtension
from flaskteroids.helpers import form_with

SCHEMA = """\
import sqlalchemy as sa
from flaskteroids.schema import Snapshot

snapshot = Snapshot()
metadata = snapshot.metadata
snapshot.create_table("authors",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("name", sa.String(), nullable=False),
    sa.Column("age", sa.Integer()),
    sa.Column("active", sa.Boolean()),
    sa.Column("password_digest", sa.String()),
    sa.Column("created_at", sa.DateTime()),
    sa.Column("updated_at", sa.DateTime()),
)
snapshot.create_table("posts",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("title", sa.String(), nullable=False),
    sa.Column("author_id", sa.Integer(), sa.ForeignKey("authors.id"), nullable=False),
)
"""


@pytest.fixture
def mapped_app(discovery_package, tmp_path):
    package = discovery_package(
        {
            "__init__.py": "",
            "schema.py": SCHEMA,
            "models/__init__.py": "",
            "models/application_model.py": (
                "from flaskteroids.model import Model\n"
                "class ApplicationModel(Model):\n"
                "    __abstract__ = True\n"
            ),
            "models/author.py": (
                "from .application_model import ApplicationModel\n"
                "from flaskteroids.model import validates, after_commit, has_secure_password, PasswordAuthenticator, has_many\n"
                "from flaskteroids.rules import rules\n"
                "@rules(validates('name', presence=True),\n"
                "       validates('age', numericality={'only_integer': True, 'allow_nil': True}),\n"
                "       has_many('posts', dependent='destroy'), has_secure_password(), after_commit('_committed'))\n"
                "class Author(ApplicationModel, PasswordAuthenticator):\n"
                "    def _committed(self):\n"
                "        from flask import current_app\n"
                "        current_app.config.setdefault('commits', []).append(self.name)\n"
            ),
            "models/post.py": (
                "from .application_model import ApplicationModel\n"
                "from flaskteroids.model import validates, belongs_to\n"
                "from flaskteroids.rules import rules\n"
                "@rules(belongs_to('author'), validates('title', presence=True))\n"
                "class Post(ApplicationModel): pass\n"
            ),
        }
    )
    app = Flask(__name__)
    app.secret_key = "test"
    app.add_url_rule("/authors/", endpoint="create_author", view_func=lambda: "")
    app.add_url_rule(
        "/authors/<int:id>/", endpoint="update_author", view_func=lambda id: ""
    )
    app.database_url = f"sqlite:///{tmp_path / 'mapped.sqlite'}"
    app.config.paths = SimpleNamespace(models=f"{package}.models")
    db = SQLAlchemyExtension(app)
    db.metadata.create_all(db.engine)
    yield app
    db.engine.dispose()


@pytest.fixture
def records(mapped_app):
    with mapped_app.app_context():
        db = mapped_app.extensions["flaskteroids.db"]
        from flaskteroids.db import session

        yield SimpleNamespace(
            app=mapped_app,
            db=db,
            session=session,
            Author=db.models["Author"],
            Post=db.models["Post"],
        )


def test_application_object_is_the_mapped_object(records):
    author = records.Author.create(name="Ada")
    native = records.session.scalar(select(records.Author))
    assert native is author is records.Author.find(author.id)
    assert inspect(author).mapper.class_ is records.Author
    assert inspect(author).identity == (author.id,)
    assert set(author.__dict__).isdisjoint({"_base_instance"})


def test_failed_update_survives_queries_other_saves_and_commit(records):
    author = records.Author.create(name="Ada")
    other = records.Author.create(name="Grace")
    records.session.commit()

    assert author.update(name="") is False
    assert author.name == ""
    assert author.errors.full_messages() == ["Field name is blank"]
    assert not records.session.is_modified(author)
    assert (
        records.session.scalar(
            select(records.Author.name).where(records.Author.id == author.id)
        )
        == "Ada"
    )
    assert records.Author.find(author.id) is author
    assert other.update(name="Katherine") is True
    records.session.commit()

    with records.db.new_session() as independent:
        assert independent.get(records.Author, author.id).name == "Ada"
        assert independent.get(records.Author, other.id).name == "Katherine"
    assert author.name == ""
    assert author.update(name="Augusta") is True
    assert not author.errors


def test_valid_unsaved_edits_and_edits_after_save_do_not_leak(records):
    author = records.Author.create(name="Ada")
    author.name = "Not saved"
    records.Post.create(title="Post", author=author)
    records.session.commit()
    assert author.name == "Not saved"
    with records.db.new_session() as independent:
        assert independent.get(records.Author, author.id).name == "Ada"
    assert author.save()
    author.name = "Still not saved"
    records.session.commit()
    with records.db.new_session() as independent:
        assert independent.get(records.Author, author.id).name == "Not saved"


def test_invalid_create_returns_unsaved_object(records):
    author = records.Author.create(name="")
    assert author.is_new_record()
    assert author.name == ""
    assert author.errors
    assert records.Author.count() == 0
    assert author.update(name="Ada") is True


def test_native_publication_is_explicit_and_bypasses_validation(records):
    author = records.Author(name="")
    assert author.apply_changes() is author
    records.session.add(author)
    records.session.flush()
    assert inspect(author).persistent
    assert records.Author.find(author.id) is author
    assert not author.errors
    assert "commits" not in records.app.config


def test_native_add_does_not_silently_insert_unpublished_constructor_input(records):
    author = records.Author(name="Ada")
    records.session.add(author)
    with pytest.raises(ProgrammerError, match="staged attributes"):
        records.session.flush()
    author.apply_changes()
    records.session.flush()
    assert author.name == "Ada"


@pytest.mark.parametrize("value", ["12", "", "12garbage", "garbage"])
def test_raw_input_and_numericality_survive_failed_submission(records, value):
    author = records.Author(name="", age=value)
    assert author.read_attribute_before_type_cast("age") == value
    assert author.save() is False
    with records.app.test_request_context():
        html = form_with(model=author, caller=lambda form: form.number_field("age"))
    assert f'value="{value}"' in html
    author.name = "Ada"
    valid = value == "12"
    assert author.save() is valid
    if not valid:
        assert "Field age is not a number" in author.errors.full_messages()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", None),
        ("0", False),
        ("OFF", False),
        ("false", False),
        ("1", True),
        (None, None),
    ],
)
def test_boolean_casting_on_the_model(records, raw, expected):
    author = records.Author.create(name="Ada", active=raw)
    assert author.active is expected
    assert author.reload().active is expected


def test_reload_discards_pending_input_without_changing_identity(records):
    author = records.Author.create(name="Ada", age="12")
    author.name = ""
    author.age = "garbage"
    assert author.save() is False
    assert author.reload() is author
    assert author.name == "Ada"
    assert author.age == 12
    assert author.attributes_before_type_cast["age"] == 12
    assert not author.errors
    assert not author.changes


def test_new_relationship_graph_is_validated_and_published(records):
    author = records.Author(name="Ada")
    post = records.Post(title="First", author=author)
    assert post.save()
    assert inspect(post).persistent and inspect(author).persistent
    assert post.author is author
    assert author.posts == [post]
    assert records.Author.find(author.id) is author


def test_invalid_new_related_record_is_not_published(records):
    author = records.Author(name="")
    post = records.Post(title="First", author=author)
    assert post.save() is False
    assert author.errors
    assert post.errors
    records.session.commit()
    assert records.Author.count() == records.Post.count() == 0


def test_relationship_cascades_use_sqlalchemy(records):
    author = records.Author.create(name="Ada", posts=[records.Post(title="First")])
    assert len(author.posts) == records.Post.count() == 1
    assert author.destroy()
    assert records.Author.count() == records.Post.count() == 0


def test_query_reuse_order_pagination_count_and_native_options(records):
    for name in ("Ada", "Grace", "Augusta"):
        records.Author.create(name=name)
    authors = records.Author.where(records.Author.name.ilike("a%"))
    assert authors.count() == 2
    assert authors.where(name="Ada").count() == 1
    assert authors.count() == 2
    page = records.Author.order(name="desc").limit(2).offset(1)
    assert [author.name for author in page.all()] == ["Augusta", "Ada"]
    assert page.count() == 2
    assert page.first().name == "Augusta"
    assert page.last().name == "Ada"
    assert records.Author.limit(0).first() is None
    assert records.Author.all().options(selectinload(records.Author.posts)).count() == 3
    assert records.session.scalars(authors.statement).all() == authors.all()
    with pytest.raises(RecordNotFoundException):
        records.Author.find(999)


@pytest.mark.parametrize("native", [False, True])
def test_facade_and_native_eager_loading_avoid_per_row_queries(records, native):
    for name in ("Ada", "Grace", "Augusta"):
        records.Author.create(name=name, posts=[records.Post(title=name)])
    records.session.expunge_all()
    queries = []

    def callback(*args):
        queries.append(args[2])

    event.listen(records.db.engine, "before_cursor_execute", callback)
    try:
        if native:
            authors = records.session.scalars(
                select(records.Author).options(selectinload(records.Author.posts))
            ).all()
        else:
            authors = records.Author.includes("posts").all()
        assert {author.posts[0].title for author in authors} == {
            "Ada",
            "Grace",
            "Augusta",
        }
        assert len(queries) == 2
    finally:
        event.remove(records.db.engine, "before_cursor_execute", callback)


def test_nested_includes_and_invalid_paths(records):
    records.Author.create(name="Ada", posts=[records.Post(title="First")])
    records.session.expunge_all()
    author = records.Author.includes("posts.author").first()
    assert author.posts[0].author is author
    with pytest.raises(AttributeError, match="Unknown relationship Author.name"):
        records.Author.includes("name")
    with pytest.raises(ValueError):
        records.Author.includes("posts..author")


def test_authentication_and_sensitive_input_exclusions(records):
    author = records.Author.create(
        name="Ada", password="secret", password_confirmation="secret"
    )
    assert author.authenticate("secret")
    assert records.Author.authenticate_by(name="Ada", password="secret") is author
    assert records.Author.authenticate_by(name="Ada", password="wrong") is None
    token = author.password_reset_token
    assert records.Author.find_by_password_reset_token(token) is author
    assert set(author.__json__()).isdisjoint(
        {"password", "password_digest", "password_confirmation", "password_reset_token"}
    )
    with records.app.test_request_context():
        html = form_with(
            model=author,
            caller=lambda form: (
                form.password_field("password") + form.text_field("password_digest")
            ),
        )
    assert 'value="secret"' not in html
    assert author.password_digest not in html
    assert "secret" not in repr(author)


def test_mixed_native_and_facade_writes_roll_back_together(records):
    records.session.commit()
    with pytest.raises(RuntimeError, match="abort"):
        with records.session.begin():
            author = records.Author.create(name="Ada")
            post = records.Post(title="First", author=author).apply_changes()
            records.session.add(post)
            records.session.flush()
            raise RuntimeError("abort")
    assert records.Author.count() == records.Post.count() == 0
    assert records.app.config.get("commits", []) == []


def test_constraint_failure_requires_rollback_and_session_can_be_reused(records):
    author = records.Author(name=None)
    with pytest.raises(IntegrityError):
        author.save(validate=False)
    records.session.rollback()
    assert records.Author.count() == 0
    assert records.Author.create(name="Ada").is_persisted()


def test_commit_callbacks_wait_for_outer_transaction(records):
    author = records.Author.create(name="Ada")
    assert records.app.config.get("commits", []) == []
    author.update(name="Augusta")
    assert records.app.config.get("commits", []) == []
    records.session.commit()
    assert records.app.config["commits"] == ["Augusta"]


def test_teardown_commits_successful_writes_but_not_failed_or_unsaved_edits(mapped_app):
    db = mapped_app.extensions["flaskteroids.db"]
    author_model = db.models["Author"]
    with mapped_app.app_context():
        author = author_model.create(name="Ada")
        other = author_model.create(name="Grace")
        assert author.update(name="") is False
        other.name = "Unsaved"
    with db.new_session() as session:
        assert session.get(author_model, author.id).name == "Ada"
        assert session.get(author_model, other.id).name == "Grace"
