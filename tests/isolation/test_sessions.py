from io import BytesIO

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from flaskteroids.attachments import Blob
from flaskteroids.db import session
from flaskteroids.exceptions import RecordNotFoundException
from tests.isolation.models.records import Author


def test_nested_same_app_contexts_have_independent_sessions(make_app):
    app = make_app("a")
    with app.app_context():
        Author.create(name="seed", passcode="secret")
    with app.app_context():
        pending = Author(name="outer").apply_changes()
        session.add(pending)
        with app.app_context():
            assert Author.count() == 1
            assert pending not in session
        assert pending in session
        assert Author.count() == 1
    with app.app_context():
        assert Author.count() == 1


def test_fresh_sessions_are_caller_managed(make_app):
    app = make_app("a")
    db = app.extensions["flaskteroids.db"]
    with db.create_session() as first, db.new_session() as second:
        pending = Author(name="pending").apply_changes()
        first.add(pending)
        assert pending in first
        assert pending not in second
        assert second.execute(select(Author)).scalars().all() == []


def test_nested_apps_commit_only_their_own_callbacks(make_app):
    a, b = make_app("a"), make_app("b")
    with a.app_context(), Author.transaction():
        Author.create(name="a", passcode="secret")
        with b.app_context(), Author.transaction():
            Author.create(name="b", passcode="secret")
            assert a.config["EVENTS"] == []
        assert b.config["EVENTS"] == [("commit", "b")]
        assert a.config["EVENTS"] == []
        assert Author.first().name == "a"
    assert a.config["EVENTS"] == [("commit", "a")]


@pytest.mark.parametrize("order", [("a", "b"), ("b", "a")])
@pytest.mark.parametrize("savepoint", ["commit", "rollback"])
@pytest.mark.parametrize("transaction", ["commit", "rollback"])
def test_nested_apps_finish_only_their_own_uploads(
    make_app, order, savepoint, transaction
):
    apps = {name: make_app(name) for name in order}
    a, b = apps["a"], apps["b"]
    with a.app_context(), Author.transaction():
        outer = Author.create(name="a", passcode="secret")
        with session.begin_nested():
            outer.avatar.attach(io=BytesIO(b"a"), filename="a.txt")
        outer_blob = outer.avatar.blob
        assert not outer_blob.service.exist(outer_blob.key)
        with b.app_context():
            session.begin()
            inner = Author.create(name="b", passcode="secret")
            nested = session.begin_nested()
            inner.avatar.attach(io=BytesIO(b"b"), filename="b.txt")
            inner_blob = inner.avatar.blob
            assert not inner_blob.service.exist(inner_blob.key)
            if savepoint == "commit":
                nested.commit()
            else:
                nested.rollback()
            assert not inner_blob.service.exist(inner_blob.key)
            assert inner.name == "b"
            assert a.config["EVENTS"] == []
            if transaction == "rollback":
                session.rollback()
            else:
                session.commit()
        assert a.config["EVENTS"] == []
        assert not outer_blob.service.exist(outer_blob.key)
        with b.app_context():
            assert Author.count() == (transaction == "commit")
            uploaded = transaction == "commit" and savepoint == "commit"
            assert inner_blob.service.exist(inner_blob.key) is uploaded
            if uploaded:
                assert Blob.find(inner_blob.id).download() == b"b"
                assert Author.first().avatar.download() == b"b"
            else:
                with pytest.raises(RecordNotFoundException):
                    Blob.find(inner_blob.id)
                if transaction == "commit":
                    assert not Author.first().avatar.attached()
        assert outer.avatar.blob.key == outer_blob.key
    assert a.config["EVENTS"] == [("commit", "a")]
    expected = [("rollback", "b")] if savepoint == "rollback" else []
    assert b.config["EVENTS"] == [*expected, (transaction, "b")]
    with a.app_context():
        assert Author.first().avatar.download() == b"a"
        assert Blob.find(outer_blob.id).download() == b"a"


def test_exception_rolls_back_only_inner_app(make_app):
    a, b = make_app("a"), make_app("b")
    with a.app_context(), Author.transaction():
        Author.create(name="a", passcode="secret")
        with pytest.raises(ValueError), b.app_context(), Author.transaction():
            Author.create(name="b", passcode="secret")
            raise ValueError("failure")
        assert b.config["EVENTS"] == [("rollback", "b")]
        assert Author.count() == 1
    assert a.config["EVENTS"] == [("commit", "a")]
    with b.app_context():
        assert Author.count() == 0


def test_commit_failure_closes_inner_session_and_restores_outer(make_app):
    app = make_app("a")
    db = app.extensions["flaskteroids.db"]
    with app.app_context():
        Author.create(name="seed", passcode="secret")
    with app.app_context():
        assert Author.count() == 1
        with pytest.raises(IntegrityError), app.app_context(), Author.transaction():
            session.add(Author(id=1, name="duplicate").apply_changes())
        assert Author.first().name == "seed"
    with db.new_session() as independent:
        assert len(independent.execute(select(Author)).scalars().all()) == 1
