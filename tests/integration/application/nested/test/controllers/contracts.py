from app.models.child import Child
from app.models.parent import Parent
from test.test_helper import IntegrationTest, patch

from flaskteroids.routes import parent_path


class NestedParametersTest(IntegrationTest):
    def setup(self):
        self.parent = Parent.create(
            name="Original", children_attributes=[{"name": "First", "quantity": 1}]
        )
        self.child = self.parent.children[0]
        self.other = Parent.create(name="Other")
        self.unrelated = self.other.children.create(name="Other child", quantity=2)

    def test_unwrapped_json_permits_nested_attributes_and_filters_ownership(self):
        patch(
            parent_path(self.parent),
            json={
                "name": "Edited",
                "children_attributes": [
                    {
                        "id": self.child.id,
                        "name": "Changed",
                        "parent_id": self.other.id,
                    }
                ],
            },
        )
        self.assert_response(303)
        assert self.child.reload().name == "Changed"
        assert self.child.parent_id == self.parent.id
        assert self.parent.reload().name == "Edited"

    def test_nested_ids_are_restricted_to_the_parents_association(self):
        patch(
            parent_path(self.parent),
            json={
                "parent": {
                    "children_attributes": [{"id": self.unrelated.id, "_destroy": True}]
                }
            },
        )
        self.assert_response(404)
        assert Child.find(self.unrelated.id).parent_id == self.other.id

    def test_nested_json_rejects_incorrect_collection_shapes(self):
        patch(
            parent_path(self.parent),
            json={"parent": {"children_attributes": {"name": "Wrong shape"}}},
        )
        self.assert_response(400)
        assert Child.count() == 2
