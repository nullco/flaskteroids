import pytest
from app.models.post import Post
from test.test_helper import IntegrationTest, delete, get, patch, post

from flaskteroids.testing.context import current_response


class ResponsesTest(IntegrationTest):
    @pytest.mark.parametrize("suffix", ["", ".json"])
    @pytest.mark.parametrize("operation", ["create", "update"])
    def test_json_validation_returns_errors_and_preserves_records(
        self, suffix, operation
    ):
        headers = {"Accept": "application/json"} if not suffix else {}
        record = Post.create(title="Existing") if operation == "update" else None
        count = Post.count()
        url = f"/posts/{record.id}{suffix}/" if record else f"/posts{suffix}/"
        send = patch if record else post
        send(url, params={"post": {"title": ""}}, headers=headers)

        self.assert_response(422)
        response = current_response()
        assert response.mimetype == "application/json"
        errors = response.get_json()
        assert isinstance(errors, list) and errors
        assert Post.count() == count
        if record:
            assert Post.find(record.id).title == "Existing"

    @pytest.mark.parametrize("suffix", ["", ".json"])
    def test_json_index_returns_empty_list(self, suffix):
        headers = {"Accept": "application/json"} if not suffix else {}
        get(f"/posts{suffix}/", headers=headers)

        self.assert_response(200)
        assert current_response().get_json() == []

    @pytest.mark.parametrize("suffix", ["", ".json"])
    def test_json_create_and_update_return_persisted_attributes(self, suffix):
        headers = {"Accept": "application/json"} if not suffix else {}
        post(f"/posts{suffix}/", params={"post": {"title": "First"}}, headers=headers)

        self.assert_response(200)
        record = Post.last()
        data = current_response().get_json()
        assert (data["id"], data["title"]) == (record.id, "First")
        patch(
            f"/posts/{record.id}{suffix}/",
            params={"post": {"title": "Second"}},
            headers=headers,
        )

        self.assert_response(200)
        data = current_response().get_json()
        assert (data["id"], data["title"]) == (record.id, "Second")

    @pytest.mark.parametrize("suffix", ["", ".json"])
    def test_partial_update_preserves_omitted_attributes(self, suffix):
        headers = {"Accept": "application/json"} if not suffix else {}
        record = Post.create(title="Existing", completed=False)
        patch(
            f"/posts/{record.id}{suffix}/",
            params={"post": {"completed": True, "id": record.id + 1000}},
            headers=headers,
        )

        self.assert_response(200)
        data = current_response().get_json()
        assert (data["id"], data["title"], data["completed"]) == (
            record.id,
            "Existing",
            True,
        )
        record.reload()
        assert record.title == "Existing"
        assert record.completed is True

    def test_json_destroy_deletes_record_and_returns_empty_response(self):
        record = Post.create(title="Existing")
        delete(f"/posts/{record.id}.json/")

        self.assert_response(204)
        assert current_response().data == b""
        assert Post.count() == 0

    @pytest.mark.parametrize("operation", ["create", "update"])
    def test_html_validation_redisplays_form_with_unprocessable_status(self, operation):
        record = Post.create(title="Existing") if operation == "update" else None
        url = f"/posts/{record.id}/" if record else "/posts/"
        send = patch if record else post
        send(url, params={"post": {"title": ""}})

        self.assert_response(422)
        assert current_response().mimetype == "text/html"
        assert "<form " in current_response().text
