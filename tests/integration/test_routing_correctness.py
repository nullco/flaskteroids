"""Public generated-application routing and form workflows."""

import json

import pytest


@pytest.fixture
def logout_result(generated_store):
    _, run = generated_store

    def submit(transport, csrf):
        result = run(transport, csrf, script="session_routing.py")
        return json.loads(result.stdout.splitlines()[-1])

    return submit


@pytest.mark.parametrize(
    "transport",
    ["verb", "form", "header"],
)
def test_session_logout_destroys_the_session(logout_result, transport):
    result = logout_result(transport, "valid")
    assert result == {"status": 302, "remaining_sessions": 0, "signed_in": False}


@pytest.mark.parametrize("transport", ["verb", "form", "header"])
@pytest.mark.parametrize("csrf", ["missing", "invalid"])
def test_session_logout_requires_a_valid_csrf_token(logout_result, transport, csrf):
    assert logout_result(transport, csrf) == {
        "status": 400,
        "remaining_sessions": 1,
        "signed_in": True,
    }


def test_authentication_helpers_resume_sessions_on_public_pages(generated_store):
    _, run = generated_store
    run(script="authentication_helpers.py")


def test_nested_model_forms_create_redisplay_and_update_subscriptions(generated_store):
    _, run = generated_store
    run(script="nested_subscriptions.py")
