from typing import ClassVar
from urllib.parse import parse_qs, urljoin, urlsplit

from app.models.post import Post
from playwright.sync_api import expect
from test.test_helper import SystemTest

from flaskteroids.routes import (
    edit_post_path,
    post_path,
    posts_path,
    preview_posts_path,
)
from flaskteroids.turbo import dom_id

STREAM_TYPE = "text/vnd.turbo-stream.html"


class TurboTest(SystemTest):
    fixtures: ClassVar[list[str]] = ["posts"]

    def setup(self):
        self.external_requests = []
        self.responses = []
        self.page.route("**/*", self._local_requests_only)
        self.page.on("response", lambda response: self.responses.append(response))
        self.record = self.posts("one")
        self.record_path = post_path(self.record)
        self.collection_path = posts_path()
        self.edit_path = edit_post_path(self.record)
        self.preview_path = preview_posts_path()
        self.frame_id = dom_id(self.record)
        self.frame = self.page.locator(f"turbo-frame#{self.frame_id}")

    def teardown(self):
        assert not self.external_requests, self.external_requests

    def _local_requests_only(self, route):
        if urlsplit(route.request.url).hostname in {"localhost", "127.0.0.1"}:
            route.continue_()
        else:
            self.external_requests.append(route.request.url)
            route.abort()

    def _workspace(self):
        self.visit(self.collection_path)
        expect(self.page.get_by_role("heading", name="Posts workspace")).to_be_visible()
        self.page.wait_for_function("typeof Turbo !== 'undefined'")
        self.page.evaluate("""() => {
            window.turboSentinel = 'preserved';
            document.querySelector('#outside').dataset.clientState = 'preserved';
        }""")

    def _assert_workspace_preserved(self):
        assert self.page.evaluate("window.turboSentinel") == "preserved"
        expect(self.page.locator("#outside")).to_have_attribute(
            "data-client-state", "preserved"
        )
        expect(
            self.page.locator(f"#{dom_id(self.posts('two'))} .post-title")
        ).to_have_text("Other post")

    def _edit(self):
        with self.page.expect_response(
            lambda response: urlsplit(response.url).path == self.edit_path
        ) as edit:
            self.frame.get_by_role("link", name="Edit post", exact=True).click()
        assert edit.value.request.headers["turbo-frame"] == self.frame_id
        expect(self.frame.get_by_label("Title")).to_have_value("Original post")

    def test_inline_edit_follows_303_and_replaces_only_the_matching_frame(self):
        self._workspace()
        self._edit()
        self._assert_workspace_preserved()
        self.frame.get_by_label("Title").fill("Saved inline")
        with self.page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and urlsplit(response.url).path == self.record_path
            )
        ) as saved:
            self.frame.get_by_role("button", name="Save post").click()
        assert saved.value.status == 303
        fields = parse_qs(saved.value.request.post_data)
        assert fields["_method"][0].upper() == "PATCH"
        assert fields["csrf_token"][0]
        assert saved.value.request.headers["x-csrf-token"]
        expect(self.frame.locator(".post-title")).to_have_text("Saved inline")
        expect(self.frame.get_by_label("Title")).to_have_count(0)
        expect(
            self.page.get_by_role("heading", name="Full post details")
        ).to_have_count(0)
        self._assert_workspace_preserved()
        assert self.record.reload().title == "Saved inline"
        followed = [
            response
            for response in self.responses
            if response.request.method == "GET"
            and urlsplit(response.url).path == self.record_path
        ]
        assert len(followed) == 1
        assert followed[0].request.headers["turbo-frame"] == self.frame_id

    def test_invalid_edit_redisplays_422_errors_and_typed_value_inside_frame(self):
        self._workspace()
        self._edit()
        self.frame.get_by_label("Title").fill("<x>")
        with self.page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and urlsplit(response.url).path == self.record_path
            )
        ) as invalid:
            self.frame.get_by_role("button", name="Save post").click()
        assert invalid.value.status == 422
        expect(self.frame.get_by_role("alert")).to_contain_text("title")
        expect(self.frame.get_by_label("Title")).to_have_value("<x>")
        expect(self.frame.locator("x")).to_have_count(0)
        self._assert_workspace_preserved()
        assert self.record.reload().title == "Original post"

    def test_lazy_frame_requests_matching_content_with_minimal_layout(self):
        self._workspace()
        assert not any(
            urlsplit(response.url).path == self.preview_path
            for response in self.responses
        )
        preview = self.page.locator("turbo-frame#preview")
        with self.page.expect_response(
            lambda response: urlsplit(response.url).path == self.preview_path
        ) as loaded:
            preview.scroll_into_view_if_needed()
        response = loaded.value
        assert response.status == 200
        assert response.request.headers["turbo-frame"] == "preview"
        expect(preview.locator("#preview-result")).to_have_text("Original post")
        expect(preview.locator("#preview-result")).to_have_attribute(
            "data-requested-frame", "preview"
        )
        expect(preview.locator("#preview-result")).to_have_attribute(
            "data-is-frame", "true"
        )
        # The generated full layout loads the local runtime; the minimal frame
        # layout omits it while retaining this view's head contribution.
        assert 'name="preview-head"' in response.text()
        assert "<script" not in response.text()
        assert "turbo/turbo.js" not in response.text()
        full = self.page.request.get(urljoin(self.page.url, self.preview_path))
        assert full.status == 200
        assert "turbo/turbo.js" in full.text()
        assert 'data-is-frame="false"' in full.text()
        assert any("/assets/turbo/turbo.js" in item.url for item in self.responses)
        self._assert_workspace_preserved()

    def test_top_target_leaves_the_frame_and_renders_the_full_destination(self):
        self._workspace()
        destination_url = urljoin(self.page.url, self.record_path)
        with self.page.expect_response(
            lambda response: urlsplit(response.url).path == self.record_path
        ) as destination:
            self.frame.get_by_role("link", name="Open full page").click()
        assert "turbo-frame" not in destination.value.request.headers
        expect(self.page).to_have_url(destination_url)
        expect(
            self.page.get_by_role("heading", name="Full post details")
        ).to_be_visible()
        expect(self.page.locator("#outside")).to_have_count(0)
        expect(self.frame.locator(".post-title")).to_have_text("Original post")

    def test_stream_form_appends_inferred_record_and_updates_other_regions_safely(self):
        self._workspace()
        title = '<img src=x onerror="window.injected = true"> A new post'
        self.page.locator("#new_post").get_by_label("Title").fill(title)
        with self.page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and urlsplit(response.url).path == self.collection_path
            )
        ) as created:
            self.page.get_by_role("button", name="Add post").click()
        assert created.value.status == 200
        assert created.value.headers["content-type"].startswith(STREAM_TYPE)
        assert STREAM_TYPE in created.value.request.headers["accept"]
        expect(self.page.locator("#posts .post-title")).to_have_text(
            ["Original post", "Other post", title]
        )
        expect(self.page.locator("#post_count")).to_have_text("3")
        expect(self.page.locator("#status")).to_have_text(title)
        expect(self.page.locator("#submission_summary p")).to_have_text(title)
        expect(self.page.locator("#submission_summary")).not_to_have_attribute(
            "data-placeholder", "true"
        )
        expect(self.page.locator("#pending")).to_have_count(0)
        expect(
            self.page.locator("#posts img, #status img, #submission_summary img")
        ).to_have_count(0)
        assert self.page.evaluate("window.injected") is None
        assert Post.last().title == title
        self._assert_workspace_preserved()

    def test_stream_delete_uses_method_override_and_updates_multiple_regions(self):
        self._workspace()
        with self.page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and urlsplit(response.url).path == self.record_path
            )
        ) as removed:
            self.frame.get_by_role("button", name="Delete post").click()
        assert removed.value.status == 200
        assert removed.value.headers["content-type"].startswith(STREAM_TYPE)
        fields = parse_qs(removed.value.request.post_data)
        assert fields["_method"][0].upper() == "DELETE"
        assert fields["csrf_token"][0]
        expect(self.frame).to_have_count(0)
        expect(self.page.locator("#post_count")).to_have_text("1")
        expect(self.page.locator("#status")).to_have_text("Post removed")
        assert Post.count() == 1
        self._assert_workspace_preserved()

    def test_opted_in_get_stream_replaces_record_with_inferred_partial(self):
        self._workspace()
        # Make server state differ from the DOM so replacing the frame is visible.
        assert self.record.update(title="Changed on server")
        self.frame.evaluate("element => element.dataset.stale = 'true'")
        with self.page.expect_response(
            lambda response: urlsplit(response.url).path.endswith("/refresh/")
        ) as refreshed:
            self.page.get_by_role("link", name="Refresh first post").click()
        assert refreshed.value.request.method == "GET"
        assert refreshed.value.request.headers["accept"].startswith(STREAM_TYPE)
        assert refreshed.value.headers["content-type"].startswith(STREAM_TYPE)
        expect(self.frame.locator(".post-title")).to_have_text("Changed on server")
        expect(self.frame).not_to_have_attribute("data-stale", "true")
        expect(self.page.locator("#status")).to_have_text("Post refreshed")
        self._assert_workspace_preserved()

    def test_normal_form_submission_falls_back_to_html_with_csrf_protection(self):
        self._workspace()
        # Public no-JavaScript workflow: a normal form POST offers only HTML.
        self.page.locator("#new_post").evaluate("form => form.dataset.turbo = 'false'")
        self.page.locator("#new_post").get_by_label("Title").fill("HTML fallback")
        with self.page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and urlsplit(response.url).path == self.collection_path
            )
        ) as created:
            self.page.get_by_role("button", name="Add post").click()
        assert created.value.status == 303
        assert STREAM_TYPE not in created.value.request.headers["accept"]
        expect(
            self.page.get_by_role("heading", name="Full post details")
        ).to_be_visible()
        expect(self.page.locator(".post-title")).to_have_text("HTML fallback")
        assert Post.last().title == "HTML fallback"
        assert self.page.evaluate("window.turboSentinel") is None
        # Prove protection really is enabled, rather than merely checking a token
        # exists in markup while the testing configuration bypasses validation.
        rejected = self.page.request.post(
            urljoin(self.page.url, self.collection_path),
            form={"post[title]": "Missing token"},
        )
        assert rejected.status == 400
        assert Post.count() == 3
