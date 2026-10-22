import pytest


def test_saved_changes_describe_typed_values_from_the_latest_save(records):
    author = records.Author.create(name="Ada", age="12")
    assert author.saved_change_to_attribute("age") == (None, 12)
    assert author.attribute_before_last_save("age") is None
    assert author.update(age="13")
    assert author.saved_change_to_attribute("age") == (12, 13)
    assert author.attribute_before_last_save("name") == "Ada"
    snapshot = author.saved_changes
    snapshot.clear()
    assert author.saved_change_to_attribute("age") == (12, 13)


def test_pending_input_and_validation_failures_preserve_saved_changes(records):
    author = records.Author.create(name="Ada", age=12)
    assert author.update(age=13)
    author.name = ""
    author.age = 14
    assert not author.save()
    assert author.saved_change_to_attribute("age") == (12, 13)
    assert author.age == 14
    assert author.update(name="Augusta")
    assert author.saved_change_to_attribute("age") == (13, 14)


def test_unchanged_save_and_reload_clear_previous_saved_changes(records):
    author = records.Author.create(name="Ada", age=12)
    assert author.update(age="12")
    assert author.saved_change_to_attribute("age") is None
    assert author.attribute_before_last_save("age") == 12
    assert author.update(age=13)
    author.reload()
    assert author.saved_changes == {}


def test_saved_changes_are_available_to_save_and_commit_callbacks(records):
    author = records.Author.create(name="Ada", age=0)
    calls = []
    records.app.config["after_persist"] = lambda record: calls.append(
        ("save", record.saved_change_to_attribute("age"))
    )
    records.app.config["committed"] = lambda record: calls.append(
        ("commit", record.saved_change_to_attribute("age"))
    )
    assert author.update(age="5")
    assert calls == [("save", (0, 5)), ("commit", (0, 5))]


@pytest.mark.parametrize("native", [False, True])
def test_commit_callbacks_query_unloaded_associations_in_the_same_session(
    records, native
):
    author = records.Author.create(name="Ada", age=0)
    post = author.posts.create(title="First")
    records.session.expunge_all()
    author = records.Author.find(author.id)
    observed = []

    def committed(record):
        observed.append(record.saved_change_to_attribute("age"))
        found = record.posts.where(title="First").first()
        assert records.Post.find(post.id) is found
        assert found.author is record
        assert found.update(title="Notified")

    records.app.config["committed"] = committed
    if native:
        records.session.commit()
        with records.session.begin():
            assert author.update(age=5)
            assert observed == []
    else:
        with records.Author.transaction():
            assert author.update(age=5)
            assert observed == []
    assert observed == [(0, 5)]
    with records.db.new_session() as independent:
        assert independent.get(records.Post, post.id).title == "Notified"


def test_commit_uses_the_latest_successful_save_in_a_transaction(records):
    author = records.Author.create(name="Ada", age=0)
    changes = []
    records.app.config["committed"] = lambda record: changes.append(
        record.saved_change_to_attribute("age")
    )
    with records.Author.transaction():
        author.update(age=5)
        author.update(age=6)
        author.name = ""
        assert not author.save()
    assert changes == [(5, 6)]


def test_rollback_clears_saved_changes_and_keeps_subsequent_saves_usable(records):
    author = records.Author.create(name="Ada", age=0)
    with pytest.raises(RuntimeError, match="abort"):
        with records.Author.transaction():
            author.update(age=5)
            assert author.saved_change_to_attribute("age") == (0, 5)
            raise RuntimeError("abort")
    assert author.saved_changes == {}
    assert author.age == 0
    assert author.update(age=2)
    assert author.saved_change_to_attribute("age") == (0, 2)


def test_savepoint_rollback_preserves_the_outer_committed_history(records):
    author = records.Author.create(name="Ada", age=0)
    changes = []
    records.app.config["committed"] = lambda record: changes.append(
        record.saved_change_to_attribute("age")
    )
    with records.Author.transaction():
        author.update(age=5)
        with pytest.raises(RuntimeError, match="abort"):
            with records.Author.transaction(requires_new=True):
                author.update(age=6)
                raise RuntimeError("abort")
    assert changes == [(0, 5)]
    assert author.saved_change_to_attribute("age") == (0, 5)


def test_failed_commit_callback_keeps_the_session_usable_after_querying(records):
    author = records.Author.create(name="Ada", age=0)

    def committed(record):
        assert record.posts.where(title="First").count() == 0
        raise RuntimeError("notification failed")

    records.app.config["committed"] = committed
    with pytest.raises(RuntimeError, match="notification failed"):
        author.update(age=5)
    records.app.config.pop("committed")
    assert author.update(age=6)
    with records.db.new_session() as independent:
        assert independent.get(records.Author, author.id).age == 6
