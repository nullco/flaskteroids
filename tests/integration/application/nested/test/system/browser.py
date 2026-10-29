from app.models.child import Child
from app.models.parent import Parent
from playwright.sync_api import expect
from test.test_helper import SystemTest

from flaskteroids.routes import edit_parent_path


class NestedFormsTest(SystemTest):
    def test_nested_edit_preserves_invalid_input_and_saves_the_corrected_graph(self):
        parent = Parent.create(
            name="Original",
            children_attributes=[
                {"name": "First", "quantity": 1},
                {"name": "Remove", "quantity": 2},
            ],
        )
        first, removed = parent.children
        self.visit(edit_parent_path(parent))
        form = self.page.locator("form")
        first_row = form.locator(f'fieldset[data-child-id="{first.id}"]')
        removed_row = form.locator(f'fieldset[data-child-id="{removed.id}"]')
        new_row = form.locator('fieldset[data-child-id="new"]')
        form.get_by_label("Name", exact=True).first.fill("Edited")
        first_row.get_by_label("Name", exact=True).fill("Changed")
        first_row.get_by_label("Quantity").fill("bad")
        removed_row.get_by_role("checkbox").check()
        new_row.get_by_label("Name", exact=True).fill("Added")
        new_row.get_by_label("Quantity").fill("3")
        with self.page.expect_response(
            lambda response: response.request.method == "POST"
        ) as invalid:
            form.get_by_role("button", name="Save family").click()
        assert invalid.value.status == 422
        expect(first_row.get_by_label("Quantity")).to_have_value("bad")
        expect(first_row.get_by_role("alert")).to_contain_text("quantity")
        expect(removed_row.get_by_role("checkbox")).to_be_checked()
        expect(new_row.get_by_label("Name", exact=True)).to_have_value("Added")
        assert parent.reload().name == "Original"
        assert first.reload().name == "First"
        assert Child.count() == 2

        first_row.get_by_label("Quantity").fill("4")
        with self.page.expect_response(
            lambda response: response.request.method == "POST"
        ) as saved:
            form.get_by_role("button", name="Save family").click()
        assert saved.value.status == 303
        expect(self.page.get_by_role("heading", name="Edited")).to_be_visible()
        expect(self.page.locator("#children li")).to_have_text(
            ["Changed: 4", "Added: 3"]
        )
        assert Child.find_by(id=removed.id) is None
        assert first.reload().quantity == 4
