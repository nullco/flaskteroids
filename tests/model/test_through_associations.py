from types import SimpleNamespace

import pytest
from sqlalchemy import Column, ForeignKey, Integer, String, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base

from flaskteroids.exceptions import ProgrammerError
from flaskteroids.model import (
    RecordInvalid,
    RecordNotFoundException,
    accepts_nested_attributes_for,
    after_commit,
    before_destroy,
    before_save,
    belongs_to,
    has_many,
    init,
    validates,
)
from tests.model.schema_support import model_base

Base = declarative_base()


class OrganizationTable(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)


class UserTable(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)


class MembershipTable(Base):
    __tablename__ = "memberships"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, server_default=text("'member'"), nullable=False)


@pytest.fixture
def network(init_models, request):
    options = getattr(request, "param", {})
    events = []
    ApplicationModel = model_base(Base)

    class Organization(ApplicationModel):
        validates("name", presence=True)
        # Forward references to join declarations are resolved during mapping.
        has_many("users", through="memberships", source="person")
        has_many("memberships", dependent="destroy")
        accepts_nested_attributes_for("memberships", allow_destroy=True)

    class User(ApplicationModel):
        validates("name", presence=True)
        if not options.get("no_inverse"):
            has_many("memberships", foreign_key="person_id", dependent="destroy")
            has_many("organizations", through="memberships")

    class Membership(ApplicationModel):
        if not options.get("no_inverse"):
            belongs_to("organization")
        belongs_to("person", class_name="User", foreign_key="person_id")
        validates("role", presence=True)
        if options.get("validate_join"):
            validates("role", length={"maximum": 2})
        before_save("_saving")
        after_commit("_committed", on="create")
        before_destroy("_destroying")

        def _saving(self):
            events.append(("save", self.role))
            if options.get("integrity_error"):
                self.role = None
            if options.get("raise"):
                raise RuntimeError("Join callback failed")
            return not options.get("halt")

        def _committed(self):
            events.append(("commit", self.role))

        def _destroying(self):
            events.append(("destroy", self.role))

    init_models(
        Base,
        [
            (OrganizationTable, Organization),
            (UserTable, User),
            (MembershipTable, Membership),
        ],
    )
    return SimpleNamespace(
        Organization=Organization, User=User, Membership=Membership, events=events
    )


def test_through_collection_reads_and_queries_its_own_targets(network):
    organization = network.Organization.create(name="One")
    other = network.Organization.create(name="Two")
    ada = network.User.create(name="Ada")
    grace = network.User.create(name="Grace")
    organization.memberships.create(person=ada)
    other.memberships.create(person=grace)
    assert list(organization.users) == [ada]
    assert list(ada.organizations) == [organization]
    assert organization.users.where(name="Ada").first() is ada
    assert organization.users.all().find(ada.id) is ada
    assert organization.users.all().count() == 1
    with pytest.raises(RecordNotFoundException):
        organization.users.all().find(grace.id)


def test_through_queries_are_lazy_and_keep_scoped_creation_values(network):
    organization = network.Organization.create(name="One")
    scope = organization.users.all()
    filtered = scope.where(name="Ada")
    ada = filtered.first_or_create()
    assert ada.is_persisted()
    assert filtered.first_or_create() is ada
    assert scope.count() == filtered.count() == 1
    grace = scope.create(name="Grace")
    assert list(scope.order(name="desc").limit(1)) == [grace]
    assert filtered.count() == 1


def test_new_through_target_builds_an_unsaved_join_graph(network):
    organization = network.Organization.new(name="One")
    ada = organization.users.new(name="Ada")
    assert list(organization.users) == [ada]
    assert organization.memberships[0].person is ada
    assert organization.memberships[0].organization is organization
    assert organization.users.all().count() == 0
    assert organization.save()
    assert ada.is_persisted()
    assert organization.reload().users[0] is ada
    assert network.events == [("save", "member"), ("commit", "member")]


@pytest.mark.parametrize("operation", ["append", "assign", "create", "build"])
def test_through_writes_create_join_models_with_callbacks(network, operation):
    organization = network.Organization.create(name="One")
    assert list(organization.users) == []
    if operation == "create":
        user = organization.users.create(name="Ada")
    elif operation == "build":
        user = organization.users.new(name="Ada")
        assert user.is_new_record()
        assert organization.save()
    else:
        user = network.User.new(name="Ada")
        if operation == "append":
            organization.users.append(user)
        else:
            organization.users = [user]
    assert user.is_persisted()
    assert list(organization.users) == [user]
    membership = network.Membership.first()
    assert membership.person is user
    assert membership.organization is organization
    assert list(user.organizations) == [organization]
    assert network.events == [("save", "member"), ("commit", "member")]


@pytest.mark.parametrize("operation", ["remove", "clear", "assign", "slice"])
def test_through_removal_deletes_joins_and_preserves_targets(network, operation):
    organization = network.Organization.create(name="One")
    ada = organization.users.create(name="Ada")
    grace = organization.users.create(name="Grace")
    network.events.clear()
    if operation == "remove":
        organization.users.remove(ada)
    elif operation == "clear":
        organization.users.clear()
    elif operation == "assign":
        organization.users = [grace]
    else:
        del organization.users[:1]
    assert network.User.count() == 2
    assert network.Membership.count() == (0 if operation == "clear" else 1)
    assert list(ada.organizations) == []
    assert list(organization.users) == ([] if operation == "clear" else [grace])
    assert network.events == []


def test_replacement_preserves_existing_join_attributes(network):
    organization = network.Organization.create(name="One")
    ada = network.User.create(name="Ada")
    membership = organization.memberships.create(person=ada, role="admin")
    grace = network.User.create(name="Grace")
    organization.users = [ada, grace]
    assert network.Membership.find(membership.id).role == "admin"
    assert organization.users == [ada, grace]
    assert organization.reload().users == [ada, grace]


def test_duplicate_targets_keep_distinct_join_records(network):
    organization = network.Organization.create(name="One")
    ada = organization.users.create(name="Ada")
    organization.users.append(ada)
    assert organization.users == [ada, ada]
    assert list(organization.users.all()) == [ada, ada]
    assert organization.users.all().count() == 2
    organization.users = [ada]
    assert network.Membership.count() == 1
    organization.users.extend([ada, ada])
    assert network.Membership.count() == 3
    organization.users.remove(ada)
    assert network.Membership.count() == 0


def test_invalid_create_returns_target_input_without_a_join(network):
    organization = network.Organization.create(name="One")
    user = organization.users.create(name="")
    assert user.is_new_record()
    assert user.errors["name"]
    assert network.User.count() == network.Membership.count() == 0
    assert organization.users == []


@pytest.mark.parametrize("operation", ["append", "assign", "extend"])
def test_invalid_collection_write_raises_and_rolls_back_the_group(network, operation):
    organization = network.Organization.create(name="One")
    ada = organization.users.create(name="Ada")
    valid = network.User.new(name="Grace")
    invalid = network.User.new(name="")
    with pytest.raises(RecordInvalid) as error:
        if operation == "append":
            organization.users.append(invalid)
        elif operation == "assign":
            organization.users = [valid, invalid]
        else:
            organization.users.extend([valid, invalid])
    assert error.value.record is invalid
    assert invalid.errors["name"]
    assert organization.users == [ada]
    assert network.User.count() == network.Membership.count() == 1


@pytest.mark.parametrize("network", [{"halt": True}], indirect=True)
def test_rejected_join_raises_and_rolls_back_new_target(network):
    organization = network.Organization.create(name="One")
    with pytest.raises(RecordInvalid) as error:
        organization.users.create(name="Ada")
    assert isinstance(error.value.record, network.Membership)
    assert network.User.count() == network.Membership.count() == 0
    assert organization.users == []


def test_through_writes_join_the_callers_transaction(network):
    organization = network.Organization.create(name="One")
    with pytest.raises(RuntimeError, match="abort"):
        with network.Organization.transaction():
            organization.users.create(name="Ada")
            assert network.events == [("save", "member")]
            raise RuntimeError("abort")
    assert network.User.count() == network.Membership.count() == 0
    assert organization.users == []


def test_through_removal_rolls_back_with_the_transaction(network):
    organization = network.Organization.create(name="One")
    ada = organization.users.create(name="Ada")
    with pytest.raises(RuntimeError, match="abort"):
        with network.Organization.transaction():
            organization.users.clear()
            raise RuntimeError("abort")
    assert organization.users == [ada]
    assert ada.organizations == [organization]


def test_direct_join_updates_are_visible_in_loaded_through_collections(network):
    organization = network.Organization.create(name="One")
    other = network.Organization.create(name="Two")
    ada = organization.users.create(name="Ada")
    grace = network.User.create(name="Grace")
    assert organization.users == [ada]
    assert ada.organizations == [organization]
    assert other.users == []
    membership = organization.memberships[0]
    assert membership.update(person=grace, organization=other)
    assert organization.users == []
    assert other.users == [grace]
    assert ada.organizations == []
    assert grace.organizations == [other]


def test_includes_preloads_through_targets_and_nested_paths(network, session, engine):
    for name in ("One", "Two"):
        organization = network.Organization.create(name=name)
        organization.users.create(name=f"{name} user")
    session.expunge_all()
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        organizations = list(network.Organization.includes("users"))
        loaded_queries = len(statements)
        assert [[user.name for user in org.users] for org in organizations] == [
            ["One user"],
            ["Two user"],
        ]
        assert len(statements) == loaded_queries
        assert loaded_queries == 3
        session.expunge_all()
        organizations = list(network.Organization.includes("users.organizations"))
        loaded_queries = len(statements)
        assert organizations[0].users[0].organizations[0] is organizations[0]
        assert len(statements) == loaded_queries
    finally:
        event.remove(engine, "before_cursor_execute", capture)


def test_new_parent_append_defers_persistence(network):
    organization = network.Organization.new(name="One")
    ada = network.User.create(name="Ada")
    organization.users.append(ada)
    assert network.Membership.count() == network.Organization.count() == 0
    assert organization.save()
    assert organization.reload().users == [ada]


def test_create_requires_a_saved_parent(network):
    organization = network.Organization.new(name="One")
    with pytest.raises(ProgrammerError, match="Save the parent"):
        organization.users.create(name="Ada")


@pytest.mark.parametrize("value", [None, "Ada", ["Ada"]])
def test_through_assignment_rejects_wrong_types_before_mutation(network, value):
    organization = network.Organization.create(name="One")
    ada = organization.users.create(name="Ada")
    with pytest.raises(TypeError):
        organization.users = value
    assert organization.users == [ada]


def test_parent_destroy_runs_join_callbacks_and_preserves_shared_targets(network):
    organization = network.Organization.create(name="One")
    ada = organization.users.create(name="Ada")
    network.events.clear()
    assert organization.destroy()
    assert network.User.find(ada.id) is ada
    assert network.Membership.count() == 0
    assert network.events == [("destroy", "member")]
    assert ada.organizations == []


@pytest.mark.parametrize(
    "options",
    [
        {"source": "user"},
        {"through": "_memberships"},
        {"through": 1},
        {"through": "memberships", "source": ""},
        {"through": "memberships", "class_name": "User"},
        {"through": "memberships", "foreign_key": "person_id"},
        {"through": "memberships", "dependent": "destroy"},
        {"through": "memberships", "autosave": True},
        {"through": "memberships", "inverse_of": "organizations"},
    ],
)
def test_through_declaration_rejects_unsupported_options(options):
    ApplicationModel = model_base(Base)

    with pytest.raises(ProgrammerError):

        class Organization(ApplicationModel):
            has_many("users", **options)

        init(Organization)


def test_nested_attributes_use_the_join_association(network):
    organization = network.Organization.create(
        name="One",
        memberships_attributes=[
            {"person": network.User.new(name="Ada"), "role": "admin"}
        ],
    )
    assert organization.is_persisted()
    assert organization.users[0].name == "Ada"
    assert organization.memberships[0].role == "admin"


@pytest.mark.parametrize("network", [{"validate_join": True}], indirect=True)
def test_invalid_join_exposes_validation_errors_and_rolls_back_target(network):
    organization = network.Organization.create(name="One")
    with pytest.raises(RecordInvalid) as error:
        organization.users.create(name="Ada")
    assert isinstance(error.value.record, network.Membership)
    assert error.value.record.errors["role"]
    assert error.value.record.person.name == "Ada"
    assert error.value.record.organization is organization
    assert network.User.count() == network.Membership.count() == 0
    assert organization.users == []
    user = network.User.create(name="Grace")
    assert organization.memberships.create(person=user, role="ok").is_persisted()
    assert organization.users == [user]


@pytest.mark.parametrize(
    "network, exception",
    [({"integrity_error": True}, IntegrityError), ({"raise": True}, RuntimeError)],
    indirect=["network"],
)
def test_join_exceptions_propagate_and_roll_back_target(network, exception):
    organization = network.Organization.create(name="One")
    with pytest.raises(exception):
        organization.users.create(name="Ada")
    assert network.User.count() == network.Membership.count() == 0
    assert organization.users == []


@pytest.mark.parametrize("network", [{"no_inverse": True}], indirect=True)
@pytest.mark.parametrize("persisted", [False, True])
def test_through_writes_support_join_associations_without_inverses(network, persisted):
    organization = network.Organization.new(name="One")
    if persisted:
        assert organization.save()
    user = network.User.new(name="Ada")
    organization.users.append(user)
    if not persisted:
        assert organization.save()
    assert organization.reload().users == [user]
    organization.users.clear()
    assert network.Membership.count() == 0
    assert network.User.count() == 1


def test_direct_join_destruction_updates_through_collections(network):
    organization = network.Organization.create(name="One")
    user = organization.users.create(name="Ada")
    assert user.organizations == [organization]
    assert organization.memberships[0].destroy()
    assert organization.users == []
    assert user.organizations == []


def test_owner_reload_discards_unsaved_through_targets(network):
    organization = network.Organization.create(name="One")
    organization.users.new(name="Ada")
    assert organization.users[0].name == "Ada"
    assert organization.reload().users == []
    assert organization.save()
    assert network.User.count() == network.Membership.count() == 0


def test_invalid_new_graph_retains_target_errors_for_correction(network):
    organization = network.Organization.new(name="One")
    user = organization.users.new(name="")
    assert not organization.save()
    assert organization.users == [user]
    assert user.errors["name"]
    assert organization.errors["memberships[0].person.name"]
    user.name = "Ada"
    assert organization.save()
    assert organization.reload().users == [user]


def test_append_saves_target_edits_without_publishing_owner_input(network):
    organization = network.Organization.create(name="One")
    user = network.User.create(name="Ada")
    organization.name = "Pending"
    user.name = "Edited"
    organization.users.append(user)
    assert user.reload().name == "Edited"
    assert organization.name == "Pending"
    assert organization.read_published_attribute("name") == "One"


@pytest.mark.parametrize(
    "through, source, join_kind",
    [
        ("missing", "person", "belongs_to"),
        ("memberships", "missing", "belongs_to"),
        ("memberships", None, "belongs_to"),
        ("memberships", "people", "has_many"),
        ("users", "person", "belongs_to"),
    ],
)
def test_mapping_rejects_invalid_through_paths(through, source, join_kind):
    ApplicationModel = model_base(Base)

    class Organization(ApplicationModel):
        has_many("memberships")
        has_many("users", through=through, source=source)

    class Membership(ApplicationModel):
        belongs_to("organization")
        if join_kind == "belongs_to":
            belongs_to("person", class_name="User", foreign_key="person_id")
        else:
            has_many("people", class_name="User", foreign_key="id")

    class User(ApplicationModel):
        pass

    with pytest.raises(ProgrammerError):
        Organization.prepare()


def test_self_referential_through_paths_keep_owners_separate(init_models):
    Schema = declarative_base()

    class PersonTable(Schema):
        __tablename__ = "people"
        id = Column(Integer, primary_key=True)
        name = Column(String)

    class FollowTable(Schema):
        __tablename__ = "follows"
        id = Column(Integer, primary_key=True)
        follower_id = Column(Integer, ForeignKey("people.id"), nullable=False)
        followed_id = Column(Integer, ForeignKey("people.id"), nullable=False)

    ApplicationModel = model_base(Schema)

    class Person(ApplicationModel):
        has_many("outgoing", class_name="Follow", foreign_key="follower_id")
        has_many("incoming", class_name="Follow", foreign_key="followed_id")
        has_many("following", through="outgoing", source="followed")
        has_many("followers", through="incoming", source="follower")

    class Follow(ApplicationModel):
        belongs_to("follower", class_name="Person", foreign_key="follower_id")
        belongs_to("followed", class_name="Person", foreign_key="followed_id")

    init_models(Schema, [(PersonTable, Person), (FollowTable, Follow)])
    ada = Person.create(name="Ada")
    grace = Person.create(name="Grace")
    ada.following.append(grace)
    assert grace.followers == [ada]
    assert ada.followers == []
    assert list(ada.following.where(name="Grace")) == [grace]
    assert Person.includes("following.followers").find(ada.id).following[0] is grace
    grace.followers.remove(ada)
    assert ada.following == []
    assert Person.count() == 2


def test_through_paths_support_custom_single_column_primary_keys(init_models):
    Schema = declarative_base()

    class OrganizationTable(Schema):
        __tablename__ = "organizations"
        code = Column(String, primary_key=True)

    class UserTable(Schema):
        __tablename__ = "users"
        token = Column(String, primary_key=True)

    class MembershipTable(Schema):
        __tablename__ = "memberships"
        id = Column(Integer, primary_key=True)
        organization_code = Column(String, ForeignKey("organizations.code"))
        user_token = Column(String, ForeignKey("users.token"))

    ApplicationModel = model_base(Schema)

    class Organization(ApplicationModel):
        has_many("memberships", foreign_key="organization_code")
        has_many("users", through="memberships")

    class User(ApplicationModel):
        pass

    class Membership(ApplicationModel):
        belongs_to("organization", foreign_key="organization_code")
        belongs_to("user", foreign_key="user_token")

    init_models(
        Schema,
        [
            (OrganizationTable, Organization),
            (UserTable, User),
            (MembershipTable, Membership),
        ],
    )
    organization = Organization.create(code="research")
    user = organization.users.create(token="ada")
    assert list(organization.users.where(token="ada")) == [user]
    assert organization.users.all().find("ada") is user
    assert organization.reload().users == [user]
    organization.users.remove(user)
    assert Membership.count() == 0
    assert User.find("ada") is user


def test_build_defers_its_join_while_another_target_is_added(network):
    organization = network.Organization.create(name="One")
    built = organization.users.new(name="Built")
    added = organization.users.create(name="Added")
    assert built.is_new_record()
    assert added.is_persisted()
    assert network.Membership.count() == 1
    assert organization.users == [built, added]
    assert organization.save()
    assert network.Membership.count() == 2
    assert organization.reload().users.all().order(name="asc").first() is added


def test_reverse_preserves_the_original_join_models(network):
    organization = network.Organization.create(name="One")
    ada = organization.users.create(name="Ada")
    grace = organization.users.create(name="Grace")
    joins = list(organization.memberships)
    organization.users.reverse()
    assert organization.users == [grace, ada]
    assert list(organization.memberships) == list(reversed(joins))
    assert network.Membership.count() == 2


def test_scope_construction_defers_database_queries(network, engine):
    organization = network.Organization.create(name="One")
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        scope = organization.users.where(name="Ada").order(name="asc").limit(5)
        assert statements == []
        assert list(scope) == []
        assert len(statements) == 1
    finally:
        event.remove(engine, "before_cursor_execute", capture)


def test_nested_attributes_reject_a_through_collection():
    ApplicationModel = model_base(Base)

    class Organization(ApplicationModel):
        has_many("users", through="memberships")
        accepts_nested_attributes_for("users")

    with pytest.raises(ProgrammerError, match="join association"):
        init(Organization)
