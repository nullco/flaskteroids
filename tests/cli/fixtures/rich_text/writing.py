import base64
import re

import pytest
from playwright.sync_api import expect
from test.test_helper import SystemTest

from flaskteroids.routes import new_post_path, posts_path

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aK1sAAAAASUVORK5CYII="
)


class WritingTest(SystemTest):
    def upload_files(self, files):
        expect(self.page.get_by_label("Content")).to_be_editable()
        with self.page.expect_file_chooser() as chooser:
            self.page.get_by_role("button", name="Upload files", exact=True).click()
        chooser.value.set_files(files)

    def wait_for_attachments(self, count=1):
        self.page.wait_for_function(
            "count => (document.querySelector('lexxy-editor').value.match(/sgid=/g) || []).length === count",
            arg=count,
        )

    def test_writing_editing_and_validation_redisplay(self):
        self.visit(posts_path())
        assert self.page.evaluate("typeof Turbo.visit") == "function"
        self.page.evaluate("window.richTextNavigation = 'retained'")
        self.click_on("New post")
        self.fill_in_rich_text_area(
            "Content", value="<p>Hello <strong>world</strong></p>"
        )
        self.click_on("Submit")
        expect(self.page.get_by_label("Content")).to_contain_text("Hello world")
        self.assert_selector("li", text="Field title is blank")
        self.fill_in("Title", value="First post")
        self.click_on("Submit")
        self.assert_selector(".lexxy-content strong", text="world")
        self.click_on("Edit this post")
        expect(self.page.get_by_label("Content")).to_contain_text("Hello world")
        self.fill_in("Title", value="")
        self.fill_in_rich_text_area("Content", value="<p>Updated <em>body</em></p>")
        self.click_on("Submit")
        expect(self.page.get_by_label("Content")).to_contain_text("Updated body")
        self.assert_selector("li", text="Field title is blank")
        self.fill_in("Title", value="Revised post")
        self.click_on("Submit")
        self.assert_selector(".lexxy-content em", text="body")
        assert self.page.evaluate("window.richTextNavigation") == "retained"

    def test_headings_tables_highlights_and_code_survive_editing(self):
        self.visit(new_post_path())
        self.fill_in("Title", value="Formatting")
        self.fill_in_rich_text_area(
            "Content",
            value="<h2>Heading</h2><p><u>Underlined</u> "
            '<mark style="background-color: var(--highlight-bg-1)">Highlight</mark></p>'
            "<table><tbody><tr><th>Column</th><td>Cell</td></tr></tbody></table>"
            '<pre data-language="python">print("hello")</pre>',
        )
        self.click_on("Submit")
        self.assert_selector(".lexxy-content h2", text="Heading")
        self.assert_selector(".lexxy-content table td", text="Cell")
        self.assert_selector(".lexxy-content u", text="Underlined")
        self.assert_selector(".lexxy-content pre", text='print("hello")')
        self.click_on("Edit this post")
        expect(self.page.get_by_label("Content")).to_contain_text("Highlight")
        self.click_on("Submit")
        self.assert_selector(".lexxy-content table", text="Column")
        highlight = self.page.locator(".lexxy-content mark")
        expect(highlight).to_have_attribute("style", re.compile("background-color"))

    def test_uploaded_files_survive_validation_redisplay_and_remain_editable(self):
        self.visit(new_post_path())
        self.upload_files(
            {"name": "report.txt", "mimeType": "text/plain", "buffer": b"A report"}
        )
        self.wait_for_attachments()
        self.click_on("Submit")
        self.assert_selector("li", text="Field title is blank")
        expect(self.page.get_by_label("Content")).to_contain_text("report.txt")
        self.fill_in("Title", value="A report")
        self.click_on("Submit")
        self.assert_selector(".attachment--file a", text="report.txt")
        self.click_on("Edit this post")
        expect(self.page.get_by_label("Content")).to_contain_text("report.txt")
        self.click_on("Submit")
        self.assert_selector(".attachment--file a", text="report.txt")

    def test_uploaded_images_render_as_a_gallery(self):
        self.visit(new_post_path())
        self.fill_in("Title", value="Gallery")
        self.upload_files(
            [
                {"name": f"image{index}.png", "mimeType": "image/png", "buffer": PNG}
                for index in range(2)
            ]
        )
        self.wait_for_attachments(2)
        self.click_on("Submit")
        gallery = self.page.locator(".attachment-gallery img")
        expect(gallery).to_have_count(2)
        assert gallery.evaluate_all(
            "images => Promise.all(images.map(async image => { await image.decode(); return image.naturalWidth }))"
        ) == [1, 1]

    def test_submit_waits_for_pending_uploads(self):
        pending = []
        self.page.route(
            "**/flaskteroids/rich_text/uploads/**", lambda route: pending.append(route)
        )
        self.visit(new_post_path())
        self.fill_in("Title", value="Wait for upload")
        with self.page.expect_request("**/flaskteroids/rich_text/uploads/**"):
            self.upload_files(
                {"name": "pending.txt", "mimeType": "text/plain", "buffer": b"Upload"}
            )
        self.click_on("Submit")
        assert self.page.url.endswith(new_post_path())
        assert pending
        pending[0].continue_()
        self.assert_selector(".attachment--file a", text="pending.txt")

    def test_removing_a_pending_attachment_cancels_its_upload(self):
        pending = []
        self.page.route(
            "**/flaskteroids/rich_text/uploads/**", lambda route: pending.append(route)
        )
        self.visit(new_post_path())
        self.fill_in("Title", value="Cancelled upload")
        with self.page.expect_request("**/flaskteroids/rich_text/uploads/**"):
            self.upload_files(
                {"name": "cancelled.txt", "mimeType": "text/plain", "buffer": b"Upload"}
            )
        expect(self.page.locator("lexxy-editor progress")).to_be_visible()
        with self.page.expect_event(
            "requestfailed",
            predicate=lambda request: "/rich_text/uploads/" in request.url,
        ):
            self.fill_in_rich_text_area("Content", value="<p>Retained text</p>")
        self.click_on("Submit")
        self.assert_selector(".lexxy-content", text="Retained text")
        expect(self.page.locator(".attachment")).to_have_count(0)

    @pytest.mark.parametrize(
        "response",
        [
            {"status": 413},
            {"status": 201, "body": "null", "content_type": "application/json"},
            {"status": 201, "body": "{}", "content_type": "application/json"},
        ],
        ids=["rejected", "null-response", "missing-attributes"],
    )
    def test_failed_uploads_block_submission_until_the_attachment_is_removed(
        self, response
    ):
        self.page.route(
            "**/flaskteroids/rich_text/uploads/**",
            lambda route: route.fulfill(**response),
        )
        self.visit(new_post_path())
        self.fill_in("Title", value="Upload failed")
        self.fill_in_rich_text_area("Content", value="<p>Keep this text</p>")
        self.upload_files(
            {"name": "large.txt", "mimeType": "text/plain", "buffer": b"Too large"}
        )
        self.assert_selector('[role="alert"]')
        self.click_on("Submit")
        assert self.page.url.endswith(new_post_path())
        self.fill_in_rich_text_area("Content", value="<p>Keep this text</p>")
        self.assert_text("Post was successfully created.")

    def test_unsigned_attachments_are_dropped_when_submitted(self):
        self.visit(new_post_path())
        self.fill_in("Title", value="Verified content")
        self.fill_in_rich_text_area(
            "Content",
            value='<p>Safe</p><action-text-attachment sgid="forged" '
            'filename="injected.txt" content-type="text/plain"></action-text-attachment>',
        )
        self.click_on("Submit")
        self.assert_selector(".lexxy-content", text="Safe")
        expect(self.page.locator(".attachment")).to_have_count(0)
