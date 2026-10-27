import re

from playwright.sync_api import expect
from test.test_helper import SystemTest

from flaskteroids.routes import new_post_path, posts_path


class WritingTest(SystemTest):
    def test_writing_editing_and_validation_redisplay(self):
        self.visit(posts_path())
        assert self.page.evaluate("typeof Turbo.visit") == "function"
        self.page.evaluate("window.richTextNavigation = 'retained'")
        self.click_on("New post")
        self.fill_in_rich_text_area(
            "Content", value="<div>Hello <strong>world</strong></div>"
        )
        self.click_on("Submit")
        expect(self.page.get_by_label("Content")).to_contain_text("Hello world")
        self.assert_selector("li", text="Field title is blank")
        self.fill_in("Title", value="First post")
        self.click_on("Submit")
        self.assert_selector(".trix-content strong", text="world")
        self.click_on("Edit this post")
        expect(self.page.get_by_label("Content")).to_contain_text("Hello world")
        self.fill_in("Title", value="")
        self.fill_in_rich_text_area("Content", value="<div>Updated <em>body</em></div>")
        self.click_on("Submit")
        expect(self.page.get_by_label("Content")).to_contain_text("Updated body")
        self.assert_selector("li", text="Field title is blank")
        self.fill_in("Title", value="Revised post")
        self.click_on("Submit")
        self.assert_selector(".trix-content em", text="body")
        assert self.page.evaluate("window.richTextNavigation") == "retained"

    def test_uploaded_files_survive_validation_redisplay_and_remain_editable(self):
        self.visit(new_post_path())
        editor = self.page.get_by_label("Content")
        expect(editor).to_be_editable()
        editor.evaluate("""element => {
            element.editor.insertFile(new File(["A report"], "report.txt", {type: "text/plain"}))
        }""")
        expect(self.page.locator('input[name="post[content]"]')).to_have_value(
            re.compile(".*sgid.*", re.S)
        )
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
        editor = self.page.get_by_label("Content")
        expect(editor).to_be_editable()
        editor.evaluate("""element => {
            const bytes = Uint8Array.from(atob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aK1sAAAAASUVORK5CYII="), character => character.charCodeAt(0))
            for (let index = 0; index < 2; index++) {
                element.editor.insertFile(new File([bytes], `image${index}.png`, {type: "image/png"}))
            }
        }""")
        self.page.wait_for_function("""() => {
            const input = document.querySelector('input[name="post[content]"]')
            return (input.value.match(/sgid/g) || []).length === 2
        }""")
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
        editor = self.page.get_by_label("Content")
        expect(editor).to_be_editable()
        with self.page.expect_request("**/flaskteroids/rich_text/uploads/**"):
            editor.evaluate("""element => {
                element.editor.insertFile(new File(["Upload"], "pending.txt", {type: "text/plain"}))
            }""")
        self.click_on("Submit")
        assert self.page.url.endswith(new_post_path())
        assert pending
        pending[0].continue_()
        self.assert_selector(".attachment--file a", text="pending.txt")

    def test_failed_uploads_block_submission_until_the_attachment_is_removed(self):
        self.page.route(
            "**/flaskteroids/rich_text/uploads/**",
            lambda route: route.fulfill(status=413),
        )
        self.visit(new_post_path())
        self.fill_in("Title", value="Upload failed")
        self.fill_in_rich_text_area("Content", value="<div>Keep this text</div>")
        editor = self.page.get_by_label("Content")
        editor.evaluate("""element => {
            element.editor.insertFile(new File(["Too large"], "large.txt", {type: "text/plain"}))
        }""")
        self.assert_selector('[role="alert"]', text="Upload failed")
        self.click_on("Submit")
        assert self.page.url.endswith(new_post_path())
        self.fill_in_rich_text_area("Content", value="<div>Keep this text</div>")
        self.assert_text("Post was successfully created.")

    def test_editor_rejects_unsigned_html_attachments(self):
        self.visit(new_post_path())
        editor = self.page.get_by_label("Content")
        expect(editor).to_be_editable()
        editor.evaluate("""element => {
            element.editor.insertAttachment(new Trix.Attachment({content: "<strong>Injected</strong>"}))
        }""")
        expect(editor).not_to_contain_text("Injected")
