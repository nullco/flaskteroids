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
            "Content", with_="<div>Hello <strong>world</strong></div>"
        )
        self.click_on("Submit")
        expect(self.page.get_by_label("Content")).to_contain_text("Hello world")
        self.assert_selector("li", text="Field title is blank")
        self.fill_in("Title", with_="First post")
        self.click_on("Submit")
        self.assert_selector(".trix-content strong", text="world")
        self.click_on("Edit this post")
        expect(self.page.get_by_label("Content")).to_contain_text("Hello world")
        self.fill_in("Title", with_="")
        self.fill_in_rich_text_area("Content", with_="<div>Updated <em>body</em></div>")
        self.click_on("Submit")
        expect(self.page.get_by_label("Content")).to_contain_text("Updated body")
        self.assert_selector("li", text="Field title is blank")
        self.fill_in("Title", with_="Revised post")
        self.click_on("Submit")
        self.assert_selector(".trix-content em", text="body")
        assert self.page.evaluate("window.richTextNavigation") == "retained"

    def test_editor_rejects_file_uploads_and_embedded_attachments(self):
        self.visit(new_post_path())
        editor = self.page.get_by_label("Content")
        expect(editor).to_be_editable()
        assert self.page.locator('[data-trix-action="attachFiles"]').count() == 0
        accepted = editor.evaluate("""element => {
            const event = new Event("trix-file-accept", { bubbles: true, cancelable: true })
            return element.dispatchEvent(event)
        }""")
        assert not accepted
        editor.evaluate("""element => {
            element.editor.insertAttachment(new Trix.Attachment({content: "<strong>Injected</strong>"}))
        }""")
        expect(editor).not_to_contain_text("Injected")
