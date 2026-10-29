from types import SimpleNamespace

import pytest
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base

from flaskteroids.exceptions import ProgrammerError
from flaskteroids.form import Form
from flaskteroids.model import (
    RecordNotFoundException,
    TooManyRecords,
    accepts_nested_attributes_for,
    after_commit,
    after_rollback,
    after_save,
    after_validation,
    before_destroy,
    before_save,
    belongs_to,
    has_many,
    has_one,
    init,
    validates,
)
from tests.model.schema_support import model_base

Base = declarative_base()


class ParentTable(Base):
    __tablename__ = "parents"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)


class ChildTable(Base):
    __tablename__ = "children"
    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("parents.id"), nullable=False)
    name = Column(String, nullable=False)
    quantity = Column(Integer)
    updated_at = Column(DateTime)


class ProfileTable(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("parents.id"))
    name = Column(String)


@pytest.fixture
def family(init_models, request):
    options = getattr(request, "param", {})
    events = []
    ApplicationModel = model_base(Base)

    class Parent(ApplicationModel):
        validates("name", presence=True)
        after_validation("_validated")
        has_many("children", autosave=options.get("autosave"))
        has_one("profile")
        if options.get("nested", True):
            accepts_nested_attributes_for(
                "children",
                allow_destroy=options.get("allow_destroy", True),
                reject_if=options.get("reject_if"),
                limit=options.get("limit"),
            )
            accepts_nested_attributes_for(
                "profile",
                allow_destroy=True,
                update_only=options.get("update_only", False),
            )

        def _reject_child(self, attributes):
            return attributes.get("name") == "Skip"

        def _validated(self):
            if options.get("validation_events"):
                events.append(("validated", bool(self.errors)))

    class Child(ApplicationModel):
        belongs_to("parent")
        if options.get("nested_parent"):
            accepts_nested_attributes_for("parent")
        validates("name", presence=True)
        validates("quantity", numericality={"only_integer": True, "allow_none": True})
        before_save("_before_save")
        after_save("_after_save")
        after_commit("_committed")
        after_rollback("_rolled_back")
        before_destroy("_before_destroy")

        def _before_save(self):
            events.append(("before_save", self.name))
            return not getattr(self, "_halt_save", False)

        def _after_save(self):
            events.append(("after_save", self.name))
            if getattr(self, "_raise_after_save", False):
                raise RuntimeError("Child callback failed")

        def _rolled_back(self):
            events.append(("rollback", self.name))

        def _committed(self):
            events.append(("commit", self.name))

        def _before_destroy(self):
            events.append(("destroy", self.name))
            return not getattr(self, "_halt_destroy", False)

    class Profile(ApplicationModel):
        belongs_to("parent")
        validates("name", presence=True)

    init_models(
        Base, [(ParentTable, Parent), (ChildTable, Child), (ProfileTable, Profile)]
    )
    return SimpleNamespace(
        Parent=Parent,
        Child=Child,
        Profile=Profile,
        events=events,
        autosave=options.get("autosave"),
    )


def test_nested_creation_runs_child_lifecycles_and_links_the_graph(family):
    parent = family.Parent.create(name="Ada", children_attributes=[{"name": "First"}])
    child = parent.children[0]
    assert child.parent is parent
    assert child.is_persisted()
    assert family.events == [
        ("before_save", "First"),
        ("after_save", "First"),
        ("commit", "First"),
    ]
    assert child.saved_change_to_attribute("name") == (None, "First")


@pytest.mark.parametrize("shape", ["list", "indexed", "single"])
def test_nested_assignment_updates_associated_records_and_builds_new_ones(
    family, shape
):
    parent = family.Parent.create(name="Ada")
    child = parent.children.create(name="First")
    attributes = {"id": str(child.id), "name": "Edited"}
    values = (
        [attributes]
        if shape == "list"
        else {"0": attributes}
        if shape == "indexed"
        else attributes
    )
    parent.children_attributes = values
    assert child.name == "Edited"
    assert child.read_published_attribute("name") == "First"
    assert parent.save()
    assert child.saved_change_to_attribute("name") == ("First", "Edited")
    assert parent.update(children_attributes=[{"name": "Second"}])
    assert [entry.name for entry in parent.children] == ["Edited", "Second"]


def test_invalid_nested_input_preserves_raw_values_errors_and_retry(family, session):
    parent = family.Parent.create(name="Ada")
    child = parent.children.create(name="First", quantity=2)
    assert not parent.update(
        name="Edited",
        children_attributes=[{"id": child.id, "quantity": "bad"}, {"name": "New"}],
    )
    assert parent.name == "Edited"
    assert parent.children[0] is child
    assert child.read_attribute_before_type_cast("quantity") == "bad"
    assert parent.errors["children[0].quantity"]
    assert child.errors["quantity"]
    assert not parent.is_valid()
    assert len(parent.errors["children[0].quantity"]) == 1
    session.commit()
    assert parent.read_published_attribute("name") == "Ada"
    assert child.read_published_attribute("quantity") == 2
    assert family.Child.count() == 1
    child.quantity = "3"
    assert parent.save()
    assert child.reload().quantity == 3
    assert family.Child.count() == 2


def test_nested_assignment_rejects_ids_outside_the_association(family):
    parent = family.Parent.create(name="Ada")
    other = family.Parent.create(name="Grace")
    child = other.children.create(name="Other")
    with pytest.raises(RecordNotFoundException):
        parent.children_attributes = [{"id": child.id, "name": "Stolen"}]
    assert child.name == "Other"
    assert list(parent.children) == []


def test_nested_creation_keeps_the_owner_authoritative(family):
    parent = family.Parent.create(name="Ada")
    other = family.Parent.create(name="Grace")
    assert parent.update(
        children_attributes=[{"name": "First", "parent_id": other.id, "parent": other}]
    )
    assert parent.children[0].reload().parent_id == parent.id


def test_nested_destruction_is_deferred_and_skips_child_validation(family):
    parent = family.Parent.create(name="Ada")
    child = parent.children.create(name="First")
    parent.children_attributes = [{"id": child.id, "name": "", "_destroy": "1"}]
    assert child.marked_for_destruction()
    assert family.Child.count() == 1
    assert parent.save()
    assert family.Child.count() == 0
    assert list(parent.children) == []
    assert ("destroy", "") in family.events


@pytest.mark.parametrize("flag", [False, "0", "false", "off", ""])
def test_false_destroy_flags_update_the_child(family, flag):
    parent = family.Parent.create(name="Ada")
    child = parent.children.create(name="First")
    assert parent.update(
        children_attributes=[{"id": child.id, "name": "Edited", "_destroy": flag}]
    )
    assert child.reload().name == "Edited"


def test_marked_new_children_are_omitted_from_persistence(family):
    parent = family.Parent.new(name="Ada", children_attributes=[{"name": "First"}])
    parent.children[0].mark_for_destruction()
    assert parent.save()
    assert list(parent.children) == []
    assert family.Child.count() == 0


@pytest.mark.parametrize("family", [{"allow_destroy": False}], indirect=True)
def test_disabled_nested_destruction_preserves_the_record(family):
    parent = family.Parent.create(name="Ada")
    child = parent.children.create(name="First")
    assert parent.update(children_attributes=[{"id": child.id, "_destroy": "1"}])
    assert family.Child.count() == 1
    assert not child.marked_for_destruction()


@pytest.mark.parametrize("family", [{"reject_if": "all_blank"}], indirect=True)
def test_blank_nested_rows_are_rejected_and_zero_is_retained(family):
    parent = family.Parent.new(
        name="Ada",
        children_attributes=[
            {"name": "  "},
            {"name": "First", "quantity": 0},
            {"name": "Ignored", "_destroy": "1"},
        ],
    )
    assert [child.name for child in parent.children] == ["First"]
    assert parent.save()


@pytest.mark.parametrize("family", [{"limit": 1}], indirect=True)
def test_nested_collection_limits_are_checked_before_assignment(family):
    parent = family.Parent.new(name="Ada")
    with pytest.raises(TooManyRecords):
        parent.children_attributes = [{"name": "First"}, {"name": "Second"}]
    assert list(parent.children) == []


@pytest.mark.parametrize("value", [None, "bad", [None], [{"name": "First"}, "bad"]])
def test_nested_collection_rejects_malformed_shapes_before_assignment(family, value):
    parent = family.Parent.new(name="Ada")
    with pytest.raises(TypeError):
        parent.children_attributes = value
    assert list(parent.children) == []


@pytest.mark.parametrize(
    "family", [{"update_only": False}, {"update_only": True}], indirect=True
)
def test_singular_nested_attributes_create_and_update_associated_records(family):
    parent = family.Parent.create(name="Ada", profile_attributes={"name": "First"})
    profile = parent.profile
    assert profile.is_persisted()
    assert parent.update(profile_attributes={"id": str(profile.id), "name": "Edited"})
    assert parent.profile is profile
    assert profile.reload().name == "Edited"


@pytest.mark.parametrize("family", [{"update_only": True}], indirect=True)
def test_update_only_edits_a_singular_association_without_an_id(family):
    parent = family.Parent.create(name="Ada", profile_attributes={"name": "First"})
    profile = parent.profile
    assert parent.update(profile_attributes={"name": "Edited"})
    assert parent.profile is profile
    assert profile.reload().name == "Edited"


def test_halted_child_save_preserves_all_rows_and_can_be_retried(family):
    parent = family.Parent.create(name="Ada", children_attributes=[{"name": "First"}])
    child = parent.children[0]
    child._halt_save = True
    assert not parent.update(
        name="Edited", children_attributes=[{"id": child.id, "name": "Changed"}]
    )
    assert parent.read_published_attribute("name") == "Ada"
    assert child.read_published_attribute("name") == "First"
    child._halt_save = False
    assert parent.save()
    assert parent.reload().name == "Edited"


def test_child_commit_callbacks_wait_for_the_outer_transaction(family):
    with family.Parent.transaction():
        parent = family.Parent.create(
            name="Ada", children_attributes=[{"name": "First"}]
        )
        assert parent.is_persisted()
        assert ("commit", "First") not in family.events
    assert ("commit", "First") in family.events


@pytest.mark.parametrize(
    "family",
    [{"nested": False, "autosave": None}, {"nested": False, "autosave": True}],
    indirect=True,
)
def test_association_autosave_is_opt_in_for_existing_children(family):
    parent = family.Parent.create(name="Ada")
    child = parent.children.create(name="First")
    child.name = "Edited"
    assert parent.save()
    expected = "Edited" if family.autosave else "First"
    assert child.read_published_attribute("name") == expected


def test_unchanged_autosave_children_skip_save_callbacks(family):
    parent = family.Parent.create(name="Ada", children_attributes=[{"name": "First"}])
    family.events.clear()
    assert parent.save()
    assert family.events == []


def test_fields_for_renders_nested_names_ids_values_and_child_errors(family):
    parent = family.Parent.create(
        name="Ada", children_attributes=[{"name": "First", "quantity": 1}]
    )
    child = parent.children[0]
    child.quantity = "bad"
    assert not parent.is_valid()
    form = Form("parent", model=parent)
    builders = []

    def fields(nested):
        builders.append(nested)
        return nested.label("quantity") + nested.number_field("quantity")

    html = str(form.fields_for("children", caller=fields))
    assert 'name="parent[children_attributes][0][quantity]"' in html
    assert 'id="parent_children_attributes_0_quantity"' in html
    assert 'value="bad"' in html
    assert f'name="parent[children_attributes][0][id]" value="{child.id}"' in html
    assert builders[0].model is child
    assert builders[0].errors["quantity"]


def test_fields_for_propagates_multipart_from_nested_builders(family):
    parent = family.Parent.new(name="Ada", children_attributes=[{"name": "First"}])
    form = Form("parent", model=parent)
    html = form.fields_for(
        "children", caller=lambda nested: nested.file_field("upload")
    )
    assert form.multipart
    assert 'type="file"' in html


def test_reload_discards_nested_input_new_children_and_destruction_marks(family):
    parent = family.Parent.create(
        name="Ada",
        children_attributes=[{"name": "First", "quantity": 1}, {"name": "Second"}],
    )
    child, removed = parent.children
    parent.assign_attributes(
        children_attributes=[
            {"id": child.id, "quantity": "bad"},
            {"id": removed.id, "_destroy": True},
            {"name": "New"},
        ]
    )
    assert not parent.save()
    assert parent.reload() is parent
    assert len(parent.children) == 2
    assert child.quantity == 1
    assert not child.errors
    assert not removed.marked_for_destruction()
    assert parent.save()
    assert family.Child.count() == 2


def test_rejected_destruction_rolls_back_the_graph_and_retains_submitted_values(family):
    parent = family.Parent.create(
        name="Ada", children_attributes=[{"name": "First"}, {"name": "Second"}]
    )
    first, second = parent.children
    second._halt_destroy = True
    assert not parent.update(
        name="Edited",
        children_attributes=[
            {"id": first.id, "_destroy": True},
            {"id": second.id, "_destroy": True},
            {"name": "New"},
        ],
    )
    assert family.Child.count() == 2
    assert parent.read_published_attribute("name") == "Ada"
    assert parent.name == "Edited"
    assert parent.errors["children"]
    assert list(parent.children)[:2] == [first, second]
    second._halt_destroy = False
    assert parent.save()
    assert parent.reload().name == "Edited"
    assert [child.name for child in parent.children] == ["New"]


def test_child_after_save_failure_rolls_back_and_runs_rollback_callbacks(family):
    parent = family.Parent.create(name="Ada", children_attributes=[{"name": "First"}])
    child = parent.children[0]
    family.events.clear()
    child._raise_after_save = True
    with pytest.raises(RuntimeError, match="Child callback failed"):
        parent.update(
            name="Edited", children_attributes=[{"id": child.id, "name": "Changed"}]
        )
    assert parent.reload().name == "Ada"
    assert child.reload().name == "First"
    assert any(event == "rollback" for event, _ in family.events)
    assert not any(event == "commit" for event, _ in family.events)
    assert child.saved_changes == {}


def test_outer_transaction_rolls_back_all_nested_writes(family):
    parent = family.Parent.create(name="Ada", children_attributes=[{"name": "First"}])
    child = parent.children[0]
    with pytest.raises(RuntimeError, match="abort"):
        with family.Parent.transaction():
            assert parent.update(
                name="Edited",
                children_attributes=[
                    {"id": child.id, "name": "Changed"},
                    {"name": "New"},
                ],
            )
            raise RuntimeError("abort")
    assert parent.reload().name == "Ada"
    assert child.reload().name == "First"
    assert family.Child.count() == 1


@pytest.mark.parametrize("family", [{"validation_events": True}], indirect=True)
def test_parent_after_validation_can_inspect_nested_errors(family):
    parent = family.Parent.new(name="Ada", children_attributes=[{"name": ""}])
    assert not parent.is_valid()
    assert ("validated", True) in family.events


@pytest.mark.parametrize(
    "family",
    [
        {"reject_if": "_reject_child"},
        {"reject_if": lambda attributes: attributes.get("name") == "Skip"},
    ],
    indirect=True,
)
def test_nested_rejection_accepts_method_names_and_callables(family):
    parent = family.Parent.new(
        name="Ada", children_attributes=[{"name": "Skip"}, {"name": "Keep"}]
    )
    assert [child.name for child in parent.children] == ["Keep"]
    assert parent.save()


@pytest.mark.parametrize(
    "family", [{"nested": False, "autosave": False}], indirect=True
)
def test_disabled_autosave_requires_an_explicit_child_save(family):
    parent = family.Parent.create(name="Ada")
    child = parent.children.new(name="First")
    assert parent.save()
    assert child.is_new_record()
    assert family.Child.count() == 0
    assert child.save()
    child.name = "Edited"
    assert parent.save()
    assert child.read_published_attribute("name") == "First"


def test_singular_nested_assignment_reuses_an_existing_unsaved_record(family):
    parent = family.Parent.new(name="Ada")
    profile = family.Profile.new(parent=parent, name="First")
    parent.profile_attributes = {"name": "Edited"}
    assert parent.profile is profile
    assert parent.save()
    assert profile.reload().name == "Edited"


def test_singular_nested_assignment_replaces_without_an_id(family):
    parent = family.Parent.create(name="Ada", profile_attributes={"name": "First"})
    previous = parent.profile
    assert parent.update(profile_attributes={"name": "Second"})
    assert parent.profile is not previous
    assert parent.profile.name == "Second"
    assert previous.reload().parent_id is None


def test_singular_nested_assignment_rejects_another_owners_id(family):
    parent = family.Parent.create(name="Ada")
    other = family.Parent.create(name="Grace", profile_attributes={"name": "Other"})
    with pytest.raises(RecordNotFoundException):
        parent.profile_attributes = {"id": other.profile.id, "name": "Stolen"}
    assert parent.profile is None


@pytest.mark.parametrize(
    "options",
    [
        {"limit": -1},
        {"limit": True},
        {"reject_if": 1},
        {"allow_destroy": "yes"},
        {"update_only": 1},
    ],
)
def test_nested_declarations_reject_invalid_options(options):
    with pytest.raises(ProgrammerError):

        class Parent:
            has_many("children")
            accepts_nested_attributes_for("children", **options)

        init(Parent)


def test_nested_declarations_require_an_existing_association():
    class Parent:
        accepts_nested_attributes_for("children")

    with pytest.raises(ProgrammerError, match="Declare association"):
        init(Parent)


def test_nested_batch_saves_run_each_child_lifecycle_once(family):
    parent = family.Parent.create(
        name="Ada", children_attributes=[{"name": str(index)} for index in range(200)]
    )
    assert parent.is_persisted()
    assert family.Child.count() == 200
    assert sum(event == "after_save" for event, _ in family.events) == 200


@pytest.mark.parametrize("family", [{"nested_parent": True}], indirect=True)
def test_nested_belongs_to_saves_an_inverse_graph_without_repeating_lifecycles(family):
    child = family.Child.create(name="First", parent_attributes={"name": "Ada"})
    assert child.is_persisted()
    parent = child.parent
    assert parent.children[0] is child
    assert parent.is_persisted()
    assert family.events.count(("after_save", "First")) == 1
    assert child.update(parent_attributes={"id": parent.id, "name": "Edited"})
    assert parent.reload().name == "Edited"


def test_fields_for_renders_singular_associations_without_collection_indices(family):
    parent = family.Parent.create(name="Ada", profile_attributes={"name": "Profile"})
    form = Form("parent", model=parent)
    html = form.fields_for("profile", caller=lambda child: child.text_field("name"))
    assert 'name="parent[profile_attributes][name]"' in html
    assert 'id="parent_profile_attributes_name"' in html
    assert 'name="parent[profile_attributes][id]"' in html


def test_fields_for_requires_an_opted_in_association(family):
    form = Form("child", model=family.Child.new())
    with pytest.raises(ProgrammerError):
        form.fields_for("parent")
