import pytest
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.person import Person
from test.test_helper import ModelTest

from flaskteroids.model import RecordInvalid


class MembershipWorkflowTest(ModelTest):
    def setup(self):
        self.organization = Organization.create(name="Research")

    def test_members_and_join_attributes_share_the_same_relationship(self):
        ada = self.organization.members.where(name="Ada").first_or_create()
        assert self.organization.members.where(name="Ada").first_or_create() is ada
        membership = self.organization.memberships[0]
        assert membership.update(role="administrator")
        grace = Person.create(name="Grace")
        self.organization.members = [ada, grace]
        assert self.organization.reload().members == [ada, grace]
        assert Membership.find(membership.id).role == "administrator"
        assert ada.organizations == [self.organization]
        loaded = Organization.includes("members.organizations").find(
            self.organization.id
        )
        assert loaded.members[0].organizations[0] is loaded

        self.organization.members.remove(ada)
        assert Person.find(ada.id) is ada
        assert Membership.count() == 1
        assert ada.reload().organizations == []

    def test_collection_queries_preserve_join_creation_and_loaded_reads(self):
        members = self.organization.members
        grace = members.order("name").create(name="Grace")
        ada = members.order("name").where(name="Ada").first_or_create()
        assert members.order("name").limit(1).first() is ada
        assert members.order("name").offset(1).first() is grace
        assert members.find(ada.id) is ada
        assert members.find_by(name="Missing") is None
        loaded = list(members.includes("organizations").order("name"))
        assert loaded == [ada, grace]
        assert loaded[0].organizations.first() is self.organization
        assert list(members) == [grace, ada]

        built = members.new(name="Built")
        assert members.is_loaded()
        assert members.count() == 2
        assert members.size() == len(members) == 3
        assert members.last() is built
        assert members.order("name").find_by(name="Built") is None
        assert self.organization.save()
        assert members.count() == Membership.count() == 3

    def test_invalid_join_rejects_the_collection_write(self):
        with pytest.raises(RecordInvalid) as error:
            self.organization.members.create(name="Blocked")
        assert isinstance(error.value.record, Membership)
        assert error.value.record.errors["person"]
        # A caught rejection does not abort the enclosing test transaction.
        assert Membership.count() == 0
        assert self.organization.members == []

    def test_nested_join_attributes_edit_relationship_data(self):
        person = Person.create(name="Ada")
        assert self.organization.update(
            memberships_attributes=[{"person": person, "role": "administrator"}]
        )
        membership = self.organization.memberships[0]
        assert self.organization.members == [person]
        assert not self.organization.update(
            memberships_attributes=[{"id": membership.id, "role": "x" * 21}]
        )
        assert self.organization.memberships[0].role == "x" * 21
        assert self.organization.errors["memberships[0].role"]
        assert self.organization.update(
            memberships_attributes=[{"id": membership.id, "role": "member"}]
        )
        assert self.organization.reload().memberships[0].role == "member"

    def test_rollback_restores_membership_and_target_creation(self):
        with pytest.raises(RuntimeError, match="abort"):
            with Organization.transaction(requires_new=True):
                self.organization.members.create(name="Ada")
                raise RuntimeError("abort")
        assert Person.count() == Membership.count() == 0
        assert self.organization.members == []
