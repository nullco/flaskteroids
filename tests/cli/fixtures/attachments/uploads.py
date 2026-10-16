from app.models.member import Member
from app.models.session import Session
from app.models.user import User
from flask import current_app
from flask import session as browser_session
from test.test_helper import IntegrationTest, fixture_file_upload, get, post

from flaskteroids.attachments import blob_path
from flaskteroids.testing.context import current_response


class UploadsTest(IntegrationTest):
    def test_authenticated_upload_creates_and_serves_attachment(self):
        user = User.create(email_address="owner@example.com", password="password")
        post(
            "/session/",
            params={"email_address": user.email_address, "password": "password"},
        )
        self.assert_response("redirect")
        get("/members/new/")
        self.assert_response("success")
        assert 'enctype="multipart/form-data"' in current_response().text
        post(
            "/members/",
            params={
                "member": {
                    "name": "Owner",
                    "avatar": fixture_file_upload("attachment.txt"),
                    "files": [
                        fixture_file_upload("attachment.txt"),
                        fixture_file_upload("attachment.txt"),
                    ],
                }
            },
        )
        self.assert_response("redirect")
        member = Member.last()
        assert member.avatar.attached()
        assert len(member.files) == 2
        assert member.avatar.download() == b"An example attachment.\n"
        with current_app.test_request_context():
            url = blob_path(member.avatar)
        get(url)
        self.assert_response("redirect")
        current_app.config.attachments.authorize = lambda blob: False
        get(url)
        self.assert_response("missing")
        current_app.config.attachments.authorize = lambda blob: bool(
            Session.find_by(id=browser_session.get("session_id"))
        )
        get(url, follow_redirects=True)
        self.assert_response("success")
        assert current_response().data == member.avatar.download()
