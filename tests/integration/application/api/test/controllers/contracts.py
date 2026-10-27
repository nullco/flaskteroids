from io import BytesIO

import pytest
from app.jobs.echo_job import EchoJob
from app.mailers.notifications_mailer import NotificationsMailer
from app.models.document import Document
from app.models.post import Post
from flask import current_app
from test.test_helper import IntegrationTest, delete, get, patch, post

from flaskteroids.attachments import Blob


class APIContractTest(IntegrationTest):
    @pytest.mark.parametrize(
        "settings",
        [
            {
                "notifications": True,
                "groups": [{"name": "editors", "limits": [1, None, False]}],
            },
            {},
            [],
            [{"theme": "dark"}, ["one", 2], None],
            "dark",
            42,
            False,
            None,
        ],
    )
    def test_create_persists_json_column(self, settings):
        response = post(
            "/posts",
            json={
                "post": {"title": "Settings", "settings": settings, "ignored": "input"}
            },
        )

        self.assert_response(201)
        assert response.get_json()["settings"] == settings
        saved = Post.find(response.get_json()["id"])
        saved.reload()
        assert saved.settings == settings

    def test_update_replaces_json_column_and_filters_other_attributes(self):
        saved = Post.create(
            title="Settings", content="Keep", settings={"original": True}
        )
        settings = {"notifications": False, "groups": [{"limits": []}]}

        response = patch(
            f"/posts/{saved.id}",
            json={"settings": settings, "ignored": "input"},
        )

        self.assert_response(200)
        assert response.get_json()["settings"] == settings
        saved.reload()
        assert saved.settings == settings
        assert saved.content == "Keep"

    def test_partial_update_preserves_omitted_json_column(self):
        settings = {"notifications": True}
        saved = Post.create(title="Original", settings=settings)

        patch(f"/posts/{saved.id}", json={"title": "Changed"})

        self.assert_response(200)
        saved.reload()
        assert saved.title == "Changed"
        assert saved.settings == settings

    def test_create_accepts_unwrapped_json_and_filters_attributes(self):
        response = post(
            "/posts", json={"title": "Hello", "content": "Body", "ignored": "input"}
        )

        self.assert_response(201)
        saved = Post.find(response.get_json()["id"])
        assert saved.title == "Hello"
        assert saved.content == "Body"
        assert response.headers["Location"] == f"/posts/{saved.id}"

    def test_create_rejects_invalid_attributes(self):
        before = Post.count()

        response = post("/posts", json={"post": {"title": ""}})

        self.assert_response(422)
        assert response.get_json()
        assert Post.count() == before

    def test_update_keeps_saved_values_after_validation_failure(self):
        saved = Post.create(title="Original", content="Keep")

        response = patch(f"/posts/{saved.id}", json={"post": {"title": ""}})

        self.assert_response(422)
        assert response.get_json()
        saved.reload()
        assert saved.title == "Original"

    def test_partial_update_leaves_omitted_fields_unchanged(self):
        saved = Post.create(title="Original", content="Keep")

        response = patch(f"/posts/{saved.id}", json={"title": "Updated"})

        self.assert_response(200)
        assert response.get_json()["title"] == "Updated"
        saved.reload()
        assert saved.content == "Keep"

    def test_path_identifier_wins_over_submitted_identifier(self):
        first = Post.create(title="First")
        second = Post.create(title="Second")

        response = patch(
            f"/posts/{first.id}", json={"id": second.id, "title": "Changed"}
        )

        self.assert_response(200)
        assert response.get_json()["id"] == first.id
        assert Post.find(second.id).title == "Second"

    def test_destroy_reports_callback_rejection(self):
        saved = Post.create(title="Protected")

        response = delete(f"/posts/{saved.id}")

        self.assert_response(422)
        assert "This post is protected" in response.get_json()
        assert Post.find(saved.id).title == "Protected"

    def test_missing_records_return_json_not_found(self):
        response = get("/posts/999999")

        self.assert_response(404)
        assert response.get_json()["status"] == 404

    def test_missing_parameters_return_json_bad_request(self):
        response = post("/posts", json={"unrecognized": "input"})

        self.assert_response(400)
        assert response.get_json()["status"] == 400

    def test_multipart_upload_is_saved_through_scaffold(self):
        response = post(
            "/documents",
            data={
                "document[name]": "Uploaded",
                "document[file]": (BytesIO(b"contents"), "example.txt"),
            },
        )

        self.assert_response(201)
        record = Document.find(response.get_json()["id"])
        assert record.file.download() == b"contents"

    def test_signed_blob_can_be_attached_with_json(self):
        blob = Blob.create_and_upload(io=BytesIO(b"contents"), filename="example.txt")

        response = post(
            "/documents", json={"name": "Uploaded", "file": blob.signed_id()}
        )

        self.assert_response(201)
        record = Document.find(response.get_json()["id"])
        assert record.file.download() == b"contents"

    def test_mailer_templates_work_without_browser_facilities(self):
        with self.assert_emails(1):
            NotificationsMailer.with_(greeting="Hello API").welcome().deliver_now()

        assert (
            "Hello API"
            in self.deliveries[-1].get_body(preferencelist=("html",)).get_content()
        )

    def test_jobs_run_in_api_application_context(self):
        with self.perform_enqueued_jobs():
            EchoJob().perform_later(value=42)

        assert current_app.config.x.job_value == 42
