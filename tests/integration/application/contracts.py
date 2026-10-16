from typing import ClassVar

from app.models.story import Story
from app.models.writer import Writer
from test.test_helper import ModelTest

from flaskteroids.db import session


class AssociationTest(ModelTest):
    def test_associations_support_creation_reassignment_and_eager_loading(self):
        writer = Writer.create(name="first")
        other = Writer.create(name="second")
        story = Story.create(title="one", writer=writer)
        assert story.writer.id == writer.id
        loaded = Writer.includes("stories").find(writer.id)
        assert [entry.id for entry in loaded.stories] == [story.id]
        assert story.update(writer=other)
        assert story.reload().writer.id == other.id
        assert len(writer.stories) == 0
        assert len(other.stories) == 1

    def test_associations_validate_children_and_destroy_unloaded_dependents(self):
        writer = Writer.create(name="parent")
        invalid = Story.new(writer=writer)
        assert invalid.save() is False
        assert invalid.errors
        writer.stories.remove(invalid)
        story = Story.create(title="child", writer=writer)
        assert writer.destroy()
        assert Story.find_by(id=story.id) is None

    def test_commit_remains_inside_the_test_transaction(self):
        writer = Writer.create(name="transaction-only")
        Story.create(title="transaction-only", writer=writer)
        session.commit()
        assert Story.find_by(title="transaction-only").writer.id == writer.id

    def test_model_tests_start_with_isolated_empty_database(self):
        assert Writer.count() == Story.count() == 0


class FixtureTest(ModelTest):
    fixtures: ClassVar[list[str]] = ["stories", "writers"]

    def test_fixtures_load_in_foreign_key_order(self):
        assert self.stories("one").writer.id == self.writers("one").id
        assert Story.create(title="after fixtures", writer=self.writers("one")).id
