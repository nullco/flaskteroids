import pytest
from sqlalchemy import event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from flaskteroids.exceptions import ProgrammerError
from flaskteroids.helpers import form_with


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
    assert author.errors
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


def test_unsaved_edits_remain_staged_across_queries_and_saves(records):
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


def test_native_add_preserves_explicit_publication_boundary(records):
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
        html = form_with(
            model=author, url="/authors", caller=lambda form: form.number_field("age")
        )
    assert f'value="{value}"' in html
    author.name = "Ada"
    valid = value == "12"
    assert author.save() is valid
    if not valid:
        assert "Field age is not a number" in author.errors.full_messages()


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


def test_graph_save_rejects_invalid_new_related_record(records):
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


def test_query_supports_native_loader_options_and_statement_execution(records):
    records.Author.create(name="Ada")
    records.Author.create(name="Grace")
    authors = records.Author.where(records.Author.name.ilike("a%")).options(
        selectinload(records.Author.posts)
    )

    assert authors.count() == 1
    native = records.session.scalars(authors.statement).all()
    assert [author.name for author in native] == ["Ada"]
    assert list(authors) == native


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
            authors = list(records.Author.includes("posts"))
        assert {author.posts[0].title for author in authors} == {
            "Ada",
            "Grace",
            "Augusta",
        }
        assert len(queries) == 2
    finally:
        event.remove(records.db.engine, "before_cursor_execute", callback)


def test_includes_loads_nested_paths_and_rejects_invalid_paths(records):
    records.Author.create(name="Ada", posts=[records.Post(title="First")])
    records.session.expunge_all()
    author = records.Author.includes("posts.author").first()
    assert author.posts[0].author is author
    with pytest.raises(AttributeError, match="Unknown relationship Author.name"):
        records.Author.includes("name")
    with pytest.raises(ValueError):
        records.Author.includes("posts..author")


def test_authentication_excludes_sensitive_input_from_serialization(records):
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
            url="/authors",
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
    records.session.begin()
    author = records.Author.create(name="Ada")
    assert records.app.config.get("commits", []) == []
    author.update(name="Augusta")
    assert records.app.config.get("commits", []) == []
    records.session.commit()
    assert records.app.config["commits"] == ["Augusta"]


def test_teardown_preserves_committed_writes_but_not_failed_or_unsaved_edits(
    mapped_app,
):
    db = mapped_app.extensions["flaskteroids.db"]
    author_model = db.models["Author"]
    with mapped_app.app_context():
        author = author_model.create(name="Ada")
        other = author_model.create(name="Grace")
        author_id, other_id = author.id, other.id
        assert author.update(name="") is False
        other.name = "Unsaved"
    with db.new_session() as session:
        assert session.get(author_model, author_id).name == "Ada"
        assert session.get(author_model, other_id).name == "Grace"


def test_standalone_save_commits_before_returning(records):
    author = records.Author.create(name="Ada")
    with records.db.new_session() as independent:
        assert independent.get(records.Author, author.id).name == "Ada"
    assert records.app.config["commits"] == ["Ada"]
    assert not records.session.in_transaction()


def test_standalone_save_commits_after_prior_reads(records):
    assert records.Author.count() == 0
    author = records.Author.create(name="Ada")
    assert records.Author.find(author.id) is author
    assert author.update(name="Augusta")
    with records.db.new_session() as independent:
        assert independent.get(records.Author, author.id).name == "Augusta"
    assert records.app.config["commits"] == ["Ada", "Augusta"]


def test_explicit_model_transaction_adopts_prior_reads_and_commits_once(records):
    assert records.Author.count() == 0
    with records.Author.transaction():
        author = records.Author.create(name="Ada")
        assert author.update(name="Augusta")
        assert records.app.config.get("commits", []) == []
        with records.db.new_session() as independent:
            assert independent.get(records.Author, author.id) is None
    assert records.app.config["commits"] == ["Augusta"]
    with records.db.new_session() as independent:
        assert independent.get(records.Author, author.id).name == "Augusta"


def test_save_leaves_native_explicit_transaction_under_caller_control(records):
    with records.session.begin():
        author = records.Author.create(name="Ada")
        with records.db.new_session() as independent:
            assert independent.get(records.Author, author.id) is None
        assert records.app.config.get("commits", []) == []
    assert records.app.config["commits"] == ["Ada"]


def test_released_native_savepoint_keeps_the_outer_transaction_explicit(records):
    assert records.Author.count() == 0
    with records.session.begin_nested():
        records.Author.create(name="Ada")
    records.Author.create(name="Grace")
    assert records.app.config.get("commits", []) == []
    with records.db.new_session() as independent:
        assert independent.scalars(select(records.Author)).all() == []
    records.session.commit()
    assert records.app.config["commits"] == ["Ada", "Grace"]


def test_after_commit_exception_preserves_data_and_cleans_up_session(records):
    def fail_after_commit(author):
        raise RuntimeError("committed callback failed")

    records.app.config["committed"] = fail_after_commit
    with pytest.raises(RuntimeError, match="committed callback failed"):
        records.Author.create(name="Ada")
    assert not records.session.in_transaction()
    records.app.config.pop("committed")
    assert records.Author.create(name="Grace").is_persisted()
    with records.db.new_session() as independent:
        assert len(independent.scalars(select(records.Author)).all()) == 2


def test_validation_failure_preserves_explicit_transaction(records):
    with records.Author.transaction():
        first = records.Author.create(name="Ada")
        invalid = records.Author.create(name="")
        assert invalid.is_new_record() and invalid.errors
        last = records.Author.create(name="Grace")
    with records.db.new_session() as independent:
        assert independent.get(records.Author, first.id).name == "Ada"
        assert independent.get(records.Author, last.id).name == "Grace"
        assert len(independent.scalars(select(records.Author)).all()) == 2


def test_exception_rolls_back_all_saves_in_explicit_transaction(records):
    with pytest.raises(RuntimeError, match="abort"):
        with records.Author.transaction():
            records.Author.create(name="Ada")
            records.Author.create(name="Grace")
            raise RuntimeError("abort")
    assert records.Author.count() == 0
    assert records.app.config.get("commits", []) == []
    assert records.app.config["rollbacks"] == ["Ada", "Grace"]


def test_nested_framework_transactions_join_without_savepoints(records):
    statements = []
    event.listen(
        records.db.engine,
        "before_cursor_execute",
        lambda connection, cursor, statement, *args: statements.append(statement),
    )
    with pytest.raises(RuntimeError, match="abort"):
        with records.Author.transaction():
            records.Author.create(name="Ada")
            with records.Author.transaction():
                records.Author.create(name="Grace")
            raise RuntimeError("abort")
    assert records.Author.count() == 0
    assert not any("SAVEPOINT" in statement.upper() for statement in statements)


def test_requires_new_rolls_back_only_the_inner_operation(records):
    with records.Author.transaction():
        first = records.Author.create(name="Ada")
        with pytest.raises(RuntimeError, match="abort"):
            with records.Author.transaction(requires_new=True):
                records.Author.create(name="Rejected")
                raise RuntimeError("abort")
        last = records.Author.create(name="Grace")
        assert records.app.config.get("commits", []) == []
        assert records.app.config["rollbacks"] == ["Rejected"]
    with records.db.new_session() as independent:
        assert independent.get(records.Author, first.id).name == "Ada"
        assert independent.get(records.Author, last.id).name == "Grace"
        assert len(independent.scalars(select(records.Author)).all()) == 2
    assert records.app.config["commits"] == ["Ada", "Grace"]


def test_outer_rollback_reverts_released_savepoint(records):
    with pytest.raises(RuntimeError, match="abort"):
        with records.Author.transaction():
            with records.Author.transaction(requires_new=True):
                records.Author.create(name="Ada")
            assert records.app.config.get("commits", []) == []
            raise RuntimeError("abort")
    assert records.Author.count() == 0
    assert records.app.config["rollbacks"] == ["Ada"]


def test_standalone_save_preserves_committed_data_after_later_failure(records):
    author = records.Author.create(name="Ada")
    author_id = author.id
    with pytest.raises(IntegrityError):
        records.Author(name=None).save(validate=False)
    assert not records.session.in_transaction()
    assert records.Author.create(name="Grace").is_persisted()
    with records.db.new_session() as independent:
        assert independent.get(records.Author, author_id).name == "Ada"
        assert len(independent.scalars(select(records.Author)).all()) == 2


def test_callback_failure_rolls_back_associated_writes(records):
    def fail_after_save(author):
        records.Post.create(title="Associated", author=author)
        raise RuntimeError("callback failed")

    records.app.config["after_persist"] = fail_after_save
    with pytest.raises(RuntimeError, match="callback failed"):
        records.Author.create(name="Ada")
    assert records.Author.count() == records.Post.count() == 0
    assert records.app.config.get("commits", []) == []


def test_halted_callback_rolls_back_nested_saves(records):
    def halt_after_other_save(author):
        records.app.config.pop("before_persist")
        records.Author.create(name="Nested")
        return False

    records.app.config["before_persist"] = halt_after_other_save
    rejected = records.Author.create(name="Rejected")
    assert rejected.is_new_record()
    assert rejected.name == "Rejected"
    assert records.Author.count() == 0
    assert records.app.config.get("commits", []) == []
    assert records.app.config["rollbacks"] == ["Nested"]


def test_standalone_graph_save_commits_all_associated_rows(records):
    post = records.Post(title="First", author=records.Author(name="Ada"))
    assert post.save()
    with records.db.new_session() as independent:
        assert independent.get(records.Post, post.id).author.name == "Ada"


def test_standalone_destroy_commits_dependent_deletions(records):
    author = records.Author.create(name="Ada", posts=[records.Post(title="First")])
    author_id, post_id = author.id, author.posts[0].id
    assert author.destroy()
    with records.db.new_session() as independent:
        assert independent.get(records.Author, author_id) is None
        assert independent.get(records.Post, post_id) is None


def test_rejected_dependent_destroy_rolls_back_earlier_deletions(records, mocker):
    author = records.Author.create(
        name="Ada", posts=[records.Post(title="First"), records.Post(title="Second")]
    )
    author_id = author.id
    destroy = records.Post.destroy
    attempts = []

    def reject_second(post):
        attempts.append(post.id)
        return destroy(post) if len(attempts) == 1 else False

    mocker.patch.object(
        records.Post, "destroy", autospec=True, side_effect=reject_second
    )
    assert author.destroy() is False
    with records.db.new_session() as independent:
        assert len(independent.get(records.Author, author_id).posts) == 2


def test_explicit_transaction_can_roll_back_destroy(records):
    author = records.Author.create(name="Ada", posts=[records.Post(title="First")])
    author_id = author.id
    with pytest.raises(RuntimeError, match="abort"):
        with records.Author.transaction():
            assert author.destroy()
            raise RuntimeError("abort")
    with records.db.new_session() as independent:
        assert len(independent.get(records.Author, author_id).posts) == 1


def test_standalone_save_preserves_committed_data_after_context_exception(mapped_app):
    db = mapped_app.extensions["flaskteroids.db"]
    author_model = db.models["Author"]
    with pytest.raises(RuntimeError, match="request failed"), mapped_app.app_context():
        author = author_model.create(name="Ada")
        author_id = author.id
        raise RuntimeError("request failed")
    with db.new_session() as independent:
        assert independent.get(author_model, author_id).name == "Ada"


def test_teardown_discards_uncommitted_native_writes(mapped_app):
    db = mapped_app.extensions["flaskteroids.db"]
    author_model = db.models["Author"].prepare()
    with mapped_app.app_context():
        from flaskteroids.db import session

        session.add(author_model(name="Native").apply_changes())
        session.flush()
    with db.new_session() as independent:
        assert independent.scalars(select(author_model)).all() == []
