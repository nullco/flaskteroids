from types import SimpleNamespace

import pytest
from sqlalchemy import delete, event, insert
from sqlalchemy.orm import Session, raiseload

from flaskteroids.model import RecordInvalid


@pytest.fixture
def graph(network, session):
    first = network.Organization.create(name="One")
    second = network.Organization.create(name="Two")
    ada = first.users.create(name="Ada")
    grace = first.users.create(name="Grace")
    first.users.append(ada)
    second.users.append(ada)
    data = SimpleNamespace(
        first=first.id,
        second=second.id,
        ada=ada.id,
        grace=grace.id,
        expected=[ada.id, ada.id, grace.id],
    )
    session.expunge_all()
    return data


@pytest.fixture
def queries(engine):
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", capture)


def test_lazy_targets_load_once_without_materializing_joins(
    network, graph, session, queries
):
    organization = (
        network.Organization.all()
        .options(raiseload(network.Organization.memberships))
        .find(graph.first)
    )
    queries.clear()
    users = list(organization.users)
    assert [user.id for user in users] == graph.expected
    assert users[0] is users[1]
    assert len(queries) == 1
    assert not organization.memberships.is_loaded()
    assert not any(
        isinstance(record, network.Membership)
        for record in session.identity_map.values()
    )
    queries.clear()
    for _ in range(5):
        assert organization.users.is_loaded()
        assert organization.users.size() == len(organization.users) == 3
        assert organization.users.first() is organization.users[0] is users[0]
        assert organization.users.last() is organization.users[-1] is users[-1]
        assert list(organization.users) == users
    assert queries == []


def test_eager_targets_batch_load_without_materializing_joins(
    network, graph, session, queries
):
    queries.clear()
    organizations = list(
        network.Organization.includes("users").options(
            raiseload(network.Organization.memberships)
        )
    )
    assert len(queries) == 2
    assert [user.id for user in organizations[0].users] == graph.expected
    assert organizations[1].users.first() is organizations[0].users.first()
    assert all(organization.users.is_loaded() for organization in organizations)
    assert all(
        not organization.memberships.is_loaded() for organization in organizations
    )
    assert not any(
        isinstance(record, network.Membership)
        for record in session.identity_map.values()
    )
    assert len(queries) == 2


def test_eager_loading_batches_large_owner_sets(network, session, queries):
    with network.Organization.transaction():
        for index in range(501):
            network.Organization.create(name=f"Organization {index}")
    session.expunge_all()
    queries.clear()
    organizations = list(network.Organization.includes("users"))
    assert len(organizations) == 501
    assert all(organization.users.is_loaded() for organization in organizations)
    assert all(organization.users.size() == 0 for organization in organizations)
    assert len(queries) == 3


def test_nested_through_preloading_batches_each_target_level(network, graph, queries):
    queries.clear()
    organizations = list(network.Organization.includes("users.organizations"))
    assert len(queries) == 3
    queries.clear()
    first = organizations[0]
    ada = first.users.first()
    assert [organization.id for organization in ada.organizations] == [
        graph.first,
        graph.first,
        graph.second,
    ]
    assert ada.organizations.first() is first
    assert not first.memberships.is_loaded()
    assert not ada.memberships.is_loaded()
    assert queries == []


def test_native_prefixes_preload_nested_through_targets(network, graph, queries):
    queries.clear()
    organizations = list(
        network.Organization.includes("memberships.person.organizations")
    )
    assert len(queries) == 4
    queries.clear()
    for organization in organizations:
        for membership in organization.memberships:
            assert membership.person.organizations.is_loaded()
            assert organization in membership.person.organizations
    assert queries == []


def test_nested_preloading_preserves_cached_order_and_unsaved_targets(
    network, graph, queries
):
    organization = network.Organization.find(graph.first)
    users = organization.users
    users.reverse()
    built = users.new(name="Built")
    before = list(users)
    loaded = network.Organization.includes("users.organizations").find(graph.first)
    assert loaded is organization
    assert list(loaded.users) == before
    assert loaded.users.last() is built
    assert built.organizations.is_loaded()
    assert built.organizations.first() is organization
    queries.clear()
    network.Organization.includes("users.organizations").find(graph.first)
    assert len(queries) == 1
    assert list(organization.users) == before


def test_repeated_nested_includes_reuse_loaded_native_and_through_targets(
    network, graph, queries
):
    organization = network.Organization.includes("users").find(graph.first)
    network.Organization.includes("users.organizations", "users.memberships").find(
        graph.first
    )
    queries.clear()
    network.Organization.includes("users.organizations", "users.memberships").find(
        graph.first
    )
    assert len(queries) == 1
    queries.clear()
    for user in organization.users:
        assert user.memberships.is_loaded()
        assert user.organizations.is_loaded()
        assert user.memberships.size()
        assert user.organizations.size()
    assert queries == []


def test_includes_keeps_a_loaded_target_until_owner_reload(network, graph, queries):
    organization = network.Organization.find(graph.first)
    before = list(organization.users)
    organization.memberships.create(person=network.User.find(graph.grace))
    queries.clear()
    network.Organization.includes("users").find(graph.first)
    assert len(queries) == 1
    assert list(organization.users) == before
    assert organization.users.count() == 4
    assert len(organization.reload().users) == 4


def test_collection_reload_refreshes_membership_without_reloading_other_collections(
    network, graph, session, queries
):
    organization = network.Organization.includes("users", "memberships").find(
        graph.first
    )
    other = network.Organization.includes("users").find(graph.second)
    memberships = list(organization.memberships)
    before = list(organization.users)
    table = network.Membership.__table__
    session.execute(
        delete(table).where(
            table.c.organization_id == graph.first,
            table.c.person_id == graph.ada,
        )
    )
    session.execute(
        insert(table).values(
            organization_id=graph.first, person_id=graph.grace, role="member"
        )
    )
    assert list(organization.users) == before
    organization.name = "Unsaved"
    users = organization.users
    queries.clear()
    assert users.reload() is users
    assert users.is_loaded()
    assert len(queries) == 1
    queries.clear()
    assert [user.id for user in users] == [graph.grace, graph.grace]
    assert users[0] is users[1]
    assert organization.name == "Unsaved"
    assert organization.memberships.is_loaded()
    assert list(organization.memberships) == memberships
    assert other.users.is_loaded()
    assert [user.id for user in other.users] == [graph.ada]
    network.Organization.includes("users").find(graph.first)
    assert len(queries) == 1


@pytest.mark.parametrize("network", [{}, {"no_inverse": True}], indirect=True)
@pytest.mark.parametrize("new_owner", [False, True])
def test_collection_reload_retains_pending_joins_for_owner_save(network, new_owner):
    organization = (
        network.Organization.new(name="One")
        if new_owner
        else network.Organization.create(name="One")
    )
    saved = network.User.create(name="Saved")
    built = organization.users.new(name="Built")
    direct = network.Membership.new(person=saved, role="admin")
    organization.memberships.append(direct)
    before = list(organization.memberships)
    assert organization.users.size() == 2
    assert list(organization.users.reload()) == []
    assert list(organization.memberships) == before
    assert direct.role == "admin"
    assert built.is_new_record()
    assert network.Membership.count() == 0
    assert organization.save()
    assert network.User.count() == network.Membership.count() == 2
    assert not built.is_new_record()
    assert organization.users.size() == 0
    assert [user.id for user in organization.users.reload()] == [saved.id, built.id]


def test_new_owner_reload_retains_foreign_key_joins_without_queries(network, queries):
    saved = network.User.create(name="Saved")
    organization = network.Organization.new(name="New")
    organization.memberships.append(network.Membership.new(person_id=saved.id))
    queries.clear()
    assert list(organization.users.reload()) == []
    assert queries == []
    assert organization.save()
    assert network.Membership.count() == 1
    assert organization.users.reload().first().id == saved.id


def test_collection_reload_preserves_pending_join_errors_and_input(network):
    organization = network.Organization.create(name="One")
    saved = network.User.create(name="Saved")
    pending = network.Membership.new(person=saved, role="")
    organization.memberships.append(pending)
    assert not organization.save()
    assert pending.errors["role"]
    assert list(organization.users.reload()) == []
    assert pending in organization.memberships
    assert pending.role == ""
    assert pending.errors["role"]
    pending.role = "member"
    assert organization.save()
    assert organization.users.reload().first().id == saved.id


def test_reloaded_collection_replacement_retains_existing_join_records(network):
    organization = network.Organization.create(name="One")
    saved = network.User.create(name="Saved")
    membership = organization.memberships.create(person=saved, role="admin")
    organization.users.reload()
    organization.users = list(organization.users)
    assert [join.id for join in organization.memberships] == [membership.id]
    assert organization.memberships.first().role == "admin"
    assert organization.users.count() == 1


@pytest.mark.parametrize("new_owner", [False, True])
def test_direct_join_reload_excludes_unsaved_graph_from_owner_save(network, new_owner):
    organization = (
        network.Organization.new(name="One")
        if new_owner
        else network.Organization.create(name="One")
    )
    built = network.User.new(name="Built")
    membership = network.Membership.new(person=built)
    organization.memberships.append(membership)
    assert list(organization.memberships.reload()) == []
    assert organization.save()
    assert network.User.count() == network.Membership.count() == 0
    assert built.is_new_record()
    assert built.name == "Built"
    assert membership.is_new_record()
    assert membership.save()
    assert network.User.count() == network.Membership.count() == 1
    assert organization.users.reload() == [built]


def test_reloaded_targets_support_association_writes(network):
    organization = network.Organization.create(name="One")
    original = organization.users.create(name="Ada")
    user = organization.users.reload().first()
    other = network.Organization.create(name="Other")
    user.organizations.append(other)
    assert [owner.id for owner in user.organizations.order("id")] == [
        organization.id,
        other.id,
    ]
    user.organizations.remove(organization)
    assert [owner.id for owner in user.organizations] == [other.id]
    assert list(organization.users.reload()) == []
    assert original.name == "Ada"
    assert network.User.count() == 1


def test_commit_callbacks_observe_updated_loaded_targets(network):
    observed = []

    def observe(membership):
        assert membership.organization.users.is_loaded()
        observed.append([user.id for user in membership.organization.users])

    network.options["commit_observer"] = observe
    organization = network.Organization.create(name="One")
    assert list(organization.users) == []
    user = organization.users.create(name="Ada")
    assert observed == [[user.id]]


@pytest.mark.parametrize("operation", ["append", "replace", "remove", "clear"])
def test_collection_mutations_update_loaded_targets(network, graph, operation):
    organization = network.Organization.includes("users").find(graph.first)
    ada = organization.users.first()
    grace = organization.users.last()
    if operation == "append":
        organization.users.append(grace)
        expected = [ada, ada, grace, grace]
    elif operation == "replace":
        organization.users = [grace, ada]
        expected = [grace, ada]
    elif operation == "remove":
        organization.users.remove(ada)
        expected = [grace]
    else:
        organization.users.clear()
        expected = []
    assert organization.users.is_loaded()
    assert list(organization.users) == expected
    assert organization.users.count() == len(expected)


@pytest.mark.parametrize("operation", ["append", "replace", "clear"])
def test_rollback_invalidates_loaded_targets_and_restores_rows(
    network, graph, operation
):
    organization = network.Organization.includes("users").find(graph.first)
    with pytest.raises(RuntimeError, match="abort"):
        with network.Organization.transaction():
            if operation == "append":
                organization.users.create(name="New")
                assert organization.users.size() == 4
            elif operation == "replace":
                organization.users = [network.User.new(name="New")]
                assert organization.users.size() == 1
            else:
                organization.users.clear()
                assert organization.users.size() == 0
            raise RuntimeError("abort")
    assert not organization.users.is_loaded()
    assert [user.id for user in organization.users] == graph.expected
    assert network.User.count() == 2


def test_savepoint_rollback_invalidates_targets_loaded_from_native_writes(
    network, graph, session
):
    organization = network.Organization.find(graph.first)
    extra = network.User.create(name="Extra")
    with network.Organization.transaction():
        with pytest.raises(RuntimeError, match="abort"):
            with network.Organization.transaction(requires_new=True):
                session.execute(
                    insert(network.Membership.__table__).values(
                        organization_id=organization.id,
                        person_id=extra.id,
                        role="member",
                    )
                )
                assert len(organization.users) == 4
                raise RuntimeError("abort")
        assert not organization.users.is_loaded()
        assert [user.id for user in organization.users] == graph.expected


def test_nested_transactions_preserve_outer_targets_and_rollback_committed_savepoints(
    network, graph
):
    organization = network.Organization.includes("users").find(graph.first)
    with pytest.raises(RuntimeError, match="outer"):
        with network.Organization.transaction():
            outer = organization.users.create(name="Outer")
            with pytest.raises(RuntimeError, match="inner"):
                with network.Organization.transaction(requires_new=True):
                    organization.users.clear()
                    raise RuntimeError("inner")
            assert [user.id for user in organization.users] == [
                *graph.expected,
                outer.id,
            ]
            with network.Organization.transaction(requires_new=True):
                organization.users.create(name="Committed savepoint")
            assert organization.users.size() == 5
            raise RuntimeError("outer")
    assert not organization.users.is_loaded()
    assert [user.id for user in organization.users] == graph.expected
    assert network.User.count() == 2


@pytest.mark.parametrize("operation", ["replace", "item"])
def test_rejected_mutations_keep_cached_membership_and_invalid_input(
    network, graph, operation
):
    organization = network.Organization.includes("users").find(graph.first)
    invalid = network.User.new(name="")
    with pytest.raises(RecordInvalid):
        if operation == "replace":
            organization.users = [network.User.new(name="Valid"), invalid]
        else:
            organization.users[0] = invalid
    assert invalid.errors["name"]
    assert [user.id for user in organization.users] == graph.expected
    assert network.User.count() == 2


@pytest.mark.parametrize("boundary", ["expire", "refresh"])
def test_native_refresh_boundaries_reset_target_state(
    network, graph, session, boundary
):
    organization = network.Organization.includes("users").find(graph.first)
    assert organization.users.is_loaded()
    getattr(session, boundary)(organization, ["name"])
    assert not organization.users.is_loaded()
    assert [user.id for user in organization.users] == graph.expected


@pytest.mark.parametrize("finder, owner", [("first", "first"), ("last", "second")])
def test_terminal_queries_preload_only_the_selected_owner(
    network, graph, session, queries, finder, owner
):
    queries.clear()
    organization = getattr(network.Organization.includes("users"), finder)()
    assert organization.id == getattr(graph, owner)
    assert organization.users.is_loaded()
    assert len(queries) == 2
    owners = [
        record
        for record in session.identity_map.values()
        if isinstance(record, network.Organization)
    ]
    assert owners == [organization]


def test_rollback_resets_targets_on_an_owner_made_transient(network):
    with pytest.raises(RuntimeError, match="abort"):
        with network.Organization.transaction():
            organization = network.Organization.new(name="One")
            user = organization.users.new(name="Ada")
            assert organization.users.first() is user
            assert organization.save()
            assert organization.users.is_loaded()
            raise RuntimeError("abort")
    assert organization.is_new_record()
    assert not organization.users.is_loaded()
    assert organization.users.count() == 0
    assert (
        network.Organization.count()
        == network.User.count()
        == network.Membership.count()
        == 0
    )


def test_target_state_is_local_to_each_session(network, graph, session):
    organization = network.Organization.includes("users").find(graph.first)
    with Session(bind=session.bind) as other:
        independent = other.get(network.Organization, graph.first)
        assert independent is not organization
        assert not independent.users.is_loaded()
    assert organization.users.is_loaded()
    assert [user.id for user in organization.users] == graph.expected


def test_native_commits_keep_loaded_membership_until_reload(network, graph, session):
    organization = network.Organization.includes("users").find(graph.first)
    session.execute(
        delete(network.Membership.__table__).where(
            network.Membership.organization_id == organization.id
        )
    )
    session.commit()
    assert organization.users.is_loaded()
    assert [user.id for user in organization.users] == graph.expected
    assert organization.users.count() == 0
    assert list(organization.reload().users) == []
