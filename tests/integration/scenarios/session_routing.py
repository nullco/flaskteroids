"""Exercise generated authentication with CSRF enabled, without test-client bypasses."""

import argparse
import json

from app.models.session import Session
from wsgi import app

from tests.integration.scenarios.routing_support import account, sign_in

parser = argparse.ArgumentParser()
parser.add_argument("transport", choices=("verb", "form", "header"))
parser.add_argument("csrf", choices=("valid", "missing", "invalid"))
args = parser.parse_args()

with account(app) as user:
    client = app.test_client()
    token = sign_in(client, user)
    with app.app_context():
        assert Session.where(user_id=user.id).count() == 1
    data = {}
    headers = {}
    if args.csrf != "missing":
        data["csrf_token"] = token if args.csrf == "valid" else "invalid"
    if args.transport == "form":
        data["_method"] = "delete"
    elif args.transport == "header":
        headers["X-HTTP-Method-Override"] = "DELETE"
    logout = client.open(
        "/session",
        method="DELETE" if args.transport == "verb" else "POST",
        data=data,
        headers=headers,
    )
    with app.app_context():
        remaining = Session.where(user_id=user.id).count()
    with client.session_transaction() as browser_session:
        signed_in = "session_id" in browser_session
    print(
        json.dumps(
            {
                "status": logout.status_code,
                "remaining_sessions": remaining,
                "signed_in": signed_in,
            }
        )
    )
