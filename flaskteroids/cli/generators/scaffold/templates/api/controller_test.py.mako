from test.test_helper import IntegrationTest, delete, get, patch, post${upload_import}
from app.models.${singular} import ${model}
from flaskteroids.routes import ${singular}_path, ${singular}_url, ${collection}_url


class ${controller}ControllerTest(IntegrationTest):
    fixtures = ["${plural}"]

    def setup(self):
        self.${singular} = self.${plural}("one")

    def test_index_returns_records(self):
        response = get(${collection}_url())

        self.assert_response(200)
        assert isinstance(response.get_json(), list)

    def test_create_persists_record(self):
        with self.assert_difference(${model}.count):
            response = post(
                ${collection}_url(),
                ${"params" if attachments else "json"}={
                    "${singular}": {
                        ${attributes}
                    }
                },
            )

        self.assert_response(201)
        assert response.headers["Location"] == ${singular}_path(${model}.last())

    def test_show_returns_record(self):
        response = get(${singular}_url(self.${singular}))

        self.assert_response(200)
        assert response.get_json()["id"] == self.${singular}.id

    def test_update_saves_attributes(self):
        patch(
            ${singular}_url(self.${singular}),
            ${"params" if attachments else "json"}={
                "${singular}": {
                    ${attributes}
                }
            },
        )

        self.assert_response(200)

    def test_destroy_removes_record(self):
        with self.assert_difference(${model}.count, by=-1):
            response = delete(${singular}_url(self.${singular}))

        self.assert_response(204)
        assert response.data == b""
