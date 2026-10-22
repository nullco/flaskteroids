import pytest
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import NO_VALUE

from flaskteroids.exceptions import ProgrammerError, RecordNotFoundException


def test_association_scope_finds_or_creates_for_its_parent(records):
    author = records.Author.create(name="Ada")
    other = records.Author.create(name="Grace")
    unrelated = other.posts.create(title="Shared")
    scope = author.posts.where(title="Shared")
    post = scope.first_or_create()
    assert post.is_persisted()
    assert post.author is author
    assert scope.first_or_create() is post
    assert list(scope) == [post]
    assert list(other.posts) == [unrelated]
    assert records.Post.count() == 2


def test_scoped_creation_preserves_filters_without_mutating_the_original(records):
    author = records.Author.create(name="Ada")
    scope = author.posts.all()
    filtered = scope.where(title="First")
    first = filtered.first_or_create()
    second = scope.create(title="Second")
    assert filtered.count() == 1
    assert scope.count() == 2
    assert first.title == "First"
    assert second.title == "Second"
    assert filtered.find(first.id) is first
    with pytest.raises(RecordNotFoundException):
        filtered.find(second.id)


def test_association_creation_keeps_the_parent_authoritative(records):
    author = records.Author.create(name="Ada")
    other = records.Author.create(name="Grace")
    post = author.posts.create(title="First", author=other, author_id=other.id)
    assert post.author is author
    assert post.reload().author_id == author.id
    assert list(other.posts) == []


def test_association_creation_returns_invalid_input_for_correction(records):
    author = records.Author.create(name="Ada")
    post = author.posts.where(title="").first_or_create()
    assert post.is_new_record()
    assert post.title == ""
    assert post.author is author
    assert post.errors
    records.session.commit()
    assert records.Post.count() == 0
    assert post.update(title="Corrected")
    assert list(author.posts) == [post]


def test_association_build_connects_an_unsaved_graph(records):
    author = records.Author.new(name="Ada")
    post = author.posts.new(title="First")
    assert post.author is author
    assert list(author.posts) == [post]
    assert author.posts.where(title="First").count() == 0
    assert author.save()
    assert post.is_persisted()


def test_association_creation_requires_a_persisted_parent(records):
    author = records.Author.new(name="Ada")
    with pytest.raises(ProgrammerError, match="Save the parent"):
        author.posts.create(title="First")
    assert records.Author.count() == records.Post.count() == 0


def test_association_scopes_query_without_loading_the_whole_collection(records):
    author = records.Author.create(name="Ada")
    records.Post.create(author=author, title="First")
    records.session.expunge_all()
    author = records.Author.find(author.id)
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(records.db.engine, "before_cursor_execute", capture)
    try:
        assert author.posts.where(title="First").first_or_create().title == "First"
        assert len(statements) == 1
        assert inspect(author).attrs.posts.loaded_value is NO_VALUE
    finally:
        event.remove(records.db.engine, "before_cursor_execute", capture)


@pytest.mark.parametrize("loaded", [False, True])
def test_association_creation_updates_sqlalchemy_collection_storage(records, loaded):
    author = records.Author.create(name="Ada")
    if loaded:
        assert list(author.posts) == []
    post = author.posts.create(title="First")
    assert list(author.posts) == [post]
    records.session.expunge_all()
    native = records.session.scalar(
        select(records.Author).options(selectinload(records.Author.posts))
    )
    assert native.posts[0].title == "First"
    native.posts = []
    assert list(native.posts) == []


def test_association_create_joins_the_callers_transaction(records):
    author = records.Author.create(name="Ada")
    with pytest.raises(RuntimeError, match="abort"):
        with records.Post.transaction():
            author.posts.where(title="First").first_or_create()
            raise RuntimeError("abort")
    assert records.Post.count() == 0
    assert list(author.posts) == []


def test_model_scope_creates_from_keyword_filters(records):
    scope = records.Author.where(name="Ada")
    author = scope.first_or_create(age="12")
    assert scope.first_or_create(age=99) is author
    assert author.name == "Ada"
    assert author.age == 12
