"""Generated authentication with CSRF enabled and real committed sessions."""

import pytest
from app.models.session import Session
from wsgi import app

from tests.integration.scenarios.routing_support import account, sign_in


@pytest.fixture
def logout_result():
    def submit(transport, csrf):
        with account(app) as user:
            client = app.test_client()
            token = sign_in(client, user)
            with app.app_context():
                assert Session.where(user_id=user.id).count() == 1
            data = {}
            headers = {}
            if csrf != "missing":
                data["csrf_token"] = token if csrf == "valid" else "invalid"
            if transport == "form":
                data["_method"] = "delete"
            elif transport == "header":
                headers["X-HTTP-Method-Override"] = "DELETE"
            logout = client.open(
                "/session",
                method="DELETE" if transport == "verb" else "POST",
                data=data,
                headers=headers,
            )
            with app.app_context():
                remaining = Session.where(user_id=user.id).count()
            with client.session_transaction() as browser_session:
                signed_in = "session_id" in browser_session
            return {
                "status": logout.status_code,
                "remaining_sessions": remaining,
                "signed_in": signed_in,
            }

    return submit


@pytest.mark.parametrize("transport", ["verb", "form", "header"])
def test_session_logout_destroys_the_session(logout_result, transport):
    assert logout_result(transport, "valid") == {
        "status": 302,
        "remaining_sessions": 0,
        "signed_in": False,
    }


@pytest.mark.parametrize("transport", ["verb", "form", "header"])
@pytest.mark.parametrize("csrf", ["missing", "invalid"])
def test_session_logout_requires_a_valid_csrf_token(logout_result, transport, csrf):
    assert logout_result(transport, csrf) == {
        "status": 400,
        "remaining_sessions": 1,
        "signed_in": True,
    }
