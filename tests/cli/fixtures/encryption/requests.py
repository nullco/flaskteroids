from typing import ClassVar

from app.models.account import Account
from test.test_helper import IntegrationTest, get, patch, post

from flaskteroids.routes import account_path, accounts_path, edit_account_path
from flaskteroids.testing.context import current_response


class EncryptionTest(IntegrationTest):
    fixtures: ClassVar[list[str]] = ["accounts"]

    def test_fixtures_encrypt_declared_attributes(self):
        account = self.accounts("one")
        assert account.notes == "My notes"
        assert account.email == "My email"
        assert "My notes" not in account.ciphertext_for("notes")
        assert Account.find_by(email="My email") is account

    def test_requests_save_and_render_plaintext(self):
        post(
            accounts_path(),
            params={
                "account": {
                    "name": "Ada",
                    "email": "ada@example.com",
                    "notes": "Confidential notes",
                }
            },
        )
        self.assert_response("redirect")
        account = Account.find_by(email="ada@example.com")
        assert account is not None
        assert account.notes == "Confidential notes"
        get(account_path(account))
        self.assert_response("success")
        assert "Confidential notes" in current_response().text
        get(edit_account_path(account))
        self.assert_response("success")
        assert "Confidential notes" in current_response().text
        assert "flaskteroids:encrypted:" not in current_response().text
        patch(account_path(account), params={"account": {"notes": "Revised notes"}})
        self.assert_response("redirect")
        assert account.reload().notes == "Revised notes"
        assert "Revised notes" not in account.ciphertext_for("notes")

    def test_failed_validation_redisplays_plaintext_without_persisting_it(self):
        account = self.accounts("one")
        original = account.notes
        patch(
            account_path(account),
            params={"account": {"name": "", "notes": "Retained draft"}},
        )
        self.assert_response(422)
        assert "Retained draft" in current_response().text
        assert account.reload().notes == original
