from types import SimpleNamespace

import pytest
from sqlalchemy import event
from sqlalchemy.orm import selectinload

from flaskteroids.model import RecordNotFoundException


@pytest.fixture(params=["direct", "through"])
def association(request):
    if request.param == "direct":
        records = request.getfixturevalue("records")
        owner_model, target_model = records.Author, records.Post
        name, field, inverse = "posts", "title", "author"
        engine = records.db.engine
    else:
        network = request.getfixturevalue("network")
        owner_model, target_model = network.Organization, network.User
        name, field, inverse = "users", "name", "memberships"
        engine = request.getfixturevalue("engine")
    owner = owner_model.create(name="One")
    return SimpleNamespace(
        owner=owner,
        owner_model=owner_model,
        target_model=target_model,
        collection=getattr(owner, name),
        name=name,
        field=field,
        inverse=inverse,
        engine=engine,
        attributes=lambda value: {field: value},
    )


@pytest.fixture
def statements(association):
    captured = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        captured.append(statement)

    event.listen(association.engine, "before_cursor_execute", capture)
    try:
        yield captured
    finally:
        event.remove(association.engine, "before_cursor_execute", capture)


def test_query_builders_are_lazy_and_immutable(association, statements):
    collection = association.collection
    zulu = collection.create(**association.attributes("Zulu"))
    alpha = collection.create(**association.attributes("Alpha"))
    association.owner.reload()
    statements.clear()
    base = collection.order(association.field)
    page = base.limit(1).offset(1)
    filtered = collection.where(**association.attributes("Alpha"))
    collection.limit(0)
    collection.offset(1)
    collection.includes(association.inverse)
    collection.options(
        selectinload(getattr(association.target_model, association.inverse))
    )
    collection.with_all_rich_text()
    collection.with_rich_text_embeds()
    assert collection.to_sql()
    assert statements == []
    assert not collection.is_loaded()
    assert list(page) == [zulu]
    assert list(base) == [alpha, zulu]
    assert list(filtered) == [alpha]
    assert not collection.is_loaded()


@pytest.mark.parametrize("builder", ["includes", "options"])
def test_collection_queries_preload_target_relationships(
    association, statements, builder
):
    collection = association.collection
    collection.create(**association.attributes("First"))
    collection.create(**association.attributes("Second"))
    association.owner.reload()
    if builder == "includes":
        query = collection.includes(association.inverse)
    else:
        query = collection.options(
            selectinload(getattr(association.target_model, association.inverse))
        )
    records = list(query)
    statements.clear()
    for record in records:
        inverse = getattr(record, association.inverse)
        if association.inverse == "memberships":
            assert list(inverse)
        else:
            assert inverse.id == association.owner.id
    assert statements == []


def test_scoped_creation_retains_ownership_after_chaining(association):
    collection = association.collection
    scope = (
        collection.order(association.field)
        .limit(5)
        .offset(0)
        .where(**association.attributes("First"))
    )
    first = scope.first_or_create()
    second = scope.create(**association.attributes("Second"))
    assert scope.first_or_create() is first
    assert association.owner.reload()
    assert list(collection.order(association.field)) == [first, second]
    assert collection.find(first.id) is first


@pytest.mark.parametrize("loaded", [False, True])
def test_finders_search_only_the_association(association, loaded):
    collection = association.collection
    first = collection.create(**association.attributes("First"))
    other = association.owner_model.create(name="Other")
    unrelated = getattr(other, association.name).create(
        **association.attributes("First")
    )
    association.owner.reload()
    if loaded:
        assert list(collection) == [first]
    assert collection.find(first.id) is first
    assert collection.find_by(**association.attributes("First")) is first
    assert (
        collection.order(association.field).find_by(**association.attributes("First"))
        is first
    )
    assert collection.find_by(**association.attributes("Missing")) is None
    with pytest.raises(RecordNotFoundException):
        collection.find(unrelated.id)


@pytest.mark.parametrize("loaded", [False, True])
def test_count_reads_persisted_rows_without_loading_the_collection(
    association, statements, loaded
):
    collection = association.collection
    first = collection.create(**association.attributes("First"))
    association.owner.reload()
    if loaded:
        assert list(collection) == [first]
    statements.clear()
    assert collection.count() == 1
    assert len(statements) == 1
    assert collection.is_loaded() is loaded


def test_size_counts_unloaded_rows_without_materializing_records(
    association, statements
):
    collection = association.collection
    collection.create(**association.attributes("First"))
    collection.create(**association.attributes("Second"))
    association.owner.reload()
    statements.clear()
    assert not collection.is_loaded()
    assert collection.size() == 2
    assert len(statements) == 1
    assert not collection.is_loaded()


def test_loaded_size_and_finders_use_collection_order_without_queries(
    association, statements
):
    collection = association.collection
    first = collection.create(**association.attributes("First"))
    second = collection.create(**association.attributes("Second"))
    assert list(collection) == [first, second]
    collection.reverse()
    statements.clear()
    assert collection.is_loaded()
    assert collection.size() == len(collection) == 2
    assert collection.first() is second
    assert collection.last() is first
    assert statements == []
    # An explicit scope still uses persisted ordering, not the reversed target.
    assert list(collection.order(association.field)) == [first, second]


def test_unloaded_finders_query_without_materializing_the_collection(
    association, statements
):
    collection = association.collection
    first = collection.create(**association.attributes("First"))
    second = collection.create(**association.attributes("Second"))
    association.owner.reload()
    statements.clear()
    assert collection.first() is first
    assert collection.last() is second
    assert len(statements) == 2
    assert not collection.is_loaded()


def test_unsaved_additions_are_visible_to_collection_reads_but_not_sql(association):
    collection = association.collection
    first = collection.create(**association.attributes("First"))
    association.owner.reload()
    built = collection.new(**association.attributes("Built"))
    assert collection.size() == 2
    assert collection.count() == 1
    assert collection.first() is first
    assert collection.last() is built
    assert len(collection) == 2
    assert list(collection.order(association.field)) == [first]
    assert association.owner.save()
    assert collection.count() == 2


def test_new_owner_reads_its_unsaved_collection_without_queries(
    association, statements
):
    owner = association.owner_model.new(name="Unsaved")
    collection = getattr(owner, association.name)
    statements.clear()
    assert collection.count() == collection.size() == 0
    assert collection.first() is collection.last() is None
    built = collection.new(**association.attributes("Built"))
    assert collection.count() == 0
    assert collection.size() == len(collection) == 1
    assert collection.first() is collection.last() is built
    assert collection.first_or_create(**association.attributes("Other")) is built
    assert statements == []


def test_empty_collection_finders_return_none(association):
    assert association.collection.first() is None
    assert association.collection.last() is None
    assert list(association.collection) == []
    assert association.collection.first() is None
    assert association.collection.last() is None


def test_collection_first_or_create_preserves_existing_records(association):
    collection = association.collection
    first = collection.first_or_create(**association.attributes("First"))
    assert collection.first_or_create(**association.attributes("Other")) is first
    assert collection.count() == 1


def test_explicit_collection_operations_preserve_target_references(association):
    collection = association.collection
    first = association.target_model.new(**association.attributes("First"))
    second = association.target_model.new(**association.attributes("Second"))
    third = association.target_model.new(**association.attributes("Third"))
    collection.append(first)
    collection.extend([second, third])
    assert list(collection) == [first, second, third]
    assert first in collection
    assert collection.index(second, 1, 3) == 1
    assert collection[1:] == [second, third]
    assert list(reversed(collection)) == [third, second, first]
    assert collection.pop(1) is second
    collection.insert(0, second)
    assert list(collection) == [second, first, third]
    collection.reverse()
    assert collection.pop() is second
    collection.remove(first)
    assert list(collection) == [third]
    collection.clear()
    assert not collection
    with pytest.raises(IndexError):
        collection.pop()


def test_partial_through_loading_keeps_query_and_loaded_state_separate(
    network, session, mocker
):
    organization = network.Organization.create(name="One")
    user = organization.users.create(name="Ada")
    organization_id, user_id = organization.id, user.id
    session.expunge_all()
    organization = network.Organization.find(organization_id)
    assert len(organization.memberships) == 1
    execute = mocker.spy(session, "execute")
    assert not organization.users.is_loaded()
    execute.assert_not_called()
    assert organization.users.size() == 1
    assert execute.call_count == 1
    assert not organization.users.is_loaded()
    assert organization.users.first().id == user_id
    assert not organization.users.is_loaded()
    network.Organization.includes("users").find(organization_id)
    assert organization.users.is_loaded()
    execute.reset_mock()
    assert organization.users.first().id == user_id
    assert organization.users.last().id == user_id
    assert organization.users.size() == 1
    execute.assert_not_called()


def test_augmented_assignment_preserves_association_writes(association):
    first = association.target_model.new(**association.attributes("First"))
    collection = association.collection
    collection += [first]
    setattr(association.owner, association.name, collection)
    assert list(association.collection) == [first]
    assert association.owner.save()
    assert association.collection.find(first.id) is first
