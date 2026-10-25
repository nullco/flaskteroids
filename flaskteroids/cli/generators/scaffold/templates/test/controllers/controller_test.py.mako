from test.test_helper import IntegrationTest, delete, get, patch, post${upload_import}
from app.models.${singular} import ${model}
from flaskteroids.routes import (
    edit_${singular}_url,
    new_${singular}_url,
    ${singular}_url,
    ${collection}_url,
)


class ${controller}ControllerTest(IntegrationTest):
    fixtures = ["${plural}"]

    def setup(self):
        self.${singular} = self.${plural}("one")

    def test_should_get_index(self):
        get(${collection}_url())

        self.assert_response("success")

    def test_should_get_new(self):
        get(new_${singular}_url())

        self.assert_response("success")

    def test_should_create_${singular}(self):
        with self.assert_difference(${model}.count):
            post(
                ${collection}_url(),
                params={
                    "${singular}": {
                        ${attributes}
                    }
                },
            )

        self.assert_redirected_to(${singular}_url(${model}.last()))

    def test_should_show_${singular}(self):
        get(${singular}_url(self.${singular}))

        self.assert_response("success")

    def test_should_get_edit(self):
        get(edit_${singular}_url(self.${singular}))

        self.assert_response("success")

    def test_should_update_${singular}(self):
        patch(
            ${singular}_url(self.${singular}),
            params={
                "${singular}": {
                    ${attributes}
                }
            },
        )

        self.assert_response(303)
        self.assert_redirected_to(${singular}_url(self.${singular}))

    def test_should_destroy_${singular}(self):
        with self.assert_difference(${model}.count, by=-1):
            delete(${singular}_url(self.${singular}))

        self.assert_response(303)
        self.assert_redirected_to(${collection}_url())
