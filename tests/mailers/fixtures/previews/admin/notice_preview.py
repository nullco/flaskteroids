from tests.mailers.fixtures.previews.notice_preview import (
    NoticePreview as BaseNoticePreview,
)


class NoticePreview(BaseNoticePreview):
    def welcome(self):
        return super().welcome()
