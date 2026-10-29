from types import SimpleNamespace

import pytest
from sqlalchemy import Column, ForeignKey, Integer, String, text
from sqlalchemy.orm import declarative_base

from flaskteroids.model import (
    accepts_nested_attributes_for,
    after_commit,
    before_destroy,
    before_save,
    belongs_to,
    has_many,
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
            if observer := options.get("commit_observer"):
                observer(self)

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
        Organization=Organization,
        User=User,
        Membership=Membership,
        events=events,
        options=options,
    )
