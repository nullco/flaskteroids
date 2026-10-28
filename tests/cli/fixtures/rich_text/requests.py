from html.parser import HTMLParser
from typing import ClassVar

from app.models.post import Post
from test.test_helper import IntegrationTest, get, patch, post

from flaskteroids.routes import post_path, posts_path
from flaskteroids.testing.context import current_response


class Tags(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.text = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


class RichTextTest(IntegrationTest):
    fixtures: ClassVar[list[str]] = ["posts"]

    def test_inline_fixtures_provide_rich_text(self):
        assert self.posts("one").content.to_plain_text() == "My content"

    def test_forged_html_is_sanitized_when_rendered(self):
        post(
            posts_path(),
            params={
                "post": {
                    "title": "Untrusted input",
                    "content": '<div onclick="evil()">Visible <strong>formatting</strong><script>evil()</script><img src=x onerror="evil()"><a href="javascript:evil()">Link</a><action-text-attachment sgid="stolen">Secret</action-text-attachment></div>',
                }
            },
        )
        self.assert_response("redirect")
        record = Post.last()
        get(post_path(record))
        self.assert_response("success")
        parsed = Tags(current_response().text)
        assert any(tag == "strong" for tag, _ in parsed.tags)
        assert "Secret" not in parsed.text
        assert not any(
            name.startswith("on")
            or (value is not None and value.startswith("javascript:"))
            for _, attrs in parsed.tags
            for name, value in attrs.items()
        )
        assert record.content.to_plain_text() == "Visible formattingLink"

    def test_partial_update_preserves_rich_text(self):
        record = self.posts("one")
        original = record.content.to_editor_html()
        patch(post_path(record), params={"post": {"title": "Updated"}})
        self.assert_response("redirect")
        assert record.reload().content.to_editor_html() == original

    def test_structured_rich_text_parameters_are_rejected(self):
        post(
            posts_path(),
            params={"post": {"title": "Invalid", "content": {"body": "Unexpected"}}},
        )
        self.assert_response(400)
