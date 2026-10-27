from flaskteroids.i18n import with_locale
from tests.mailers.fixtures.preview_support import BasePreview, PreviewNoticesMailer


class NoticePreview(BasePreview):
    def welcome(self):
        greeting = self.params.pop("greeting", "Hello")
        return PreviewNoticesMailer.with_(
            name=self.params.get("name", "Jane"), greeting=greeting
        ).welcome()

    def long_name(self):
        return PreviewNoticesMailer.with_(name="A very long display name").welcome()

    def localized(self):
        with with_locale(self.params.get("locale", "en")):
            return PreviewNoticesMailer.with_().welcome()

    def text_only(self):
        return PreviewNoticesMailer.with_().text_only()

    def html_only(self):
        return PreviewNoticesMailer.with_().html_only()

    def empty(self):
        return PreviewNoticesMailer.with_().empty()

    def unsafe(self):
        return PreviewNoticesMailer.with_(greeting=self.params.get("greeting")).unsafe()

    def invalid(self):
        return None

    def broken(self):
        raise ValueError("Invalid preview data")

    def _hidden(self):
        raise AssertionError("Private preview helper invoked")
