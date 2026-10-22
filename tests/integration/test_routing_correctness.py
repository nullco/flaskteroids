"""Public generated-application routing and form workflows."""

import json
import shutil
from pathlib import Path

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


def test_generated_login_reports_rate_limiting_with_its_controller_handler(
    generated_store,
):
    _, run = generated_store
    run(script="rate_limited_login.py")


def test_password_reset_mail_uses_parameterized_inputs_outside_the_request(
    generated_store,
):
    _, run = generated_store
    run(script="parameterized_password_reset.py")


def test_queued_mail_helpers_load_in_a_fresh_worker_process(generated_store, tmp_path):
    _, run = generated_store
    payload = str(tmp_path / "mail-job.json")
    run("enqueue", payload, script="mailer_helpers.py")
    run("deliver", payload, script="mailer_helpers.py")


def test_helper_changes_load_after_application_process_restart(generated_store):
    root, run = generated_store
    helper = root / "app/helpers/application_helper.py"
    added = root / "app/helpers/notice_helper.py"
    original = helper.read_text()
    run("Store", "-", script="helper_loading.py")
    try:
        helper.write_text(original.replace('"Store"', '"Updated Store"'))
        shutil.copyfile(Path(__file__).parent / "application/notice_helper.py", added)
        run("Updated Store", "New helper loaded", script="helper_loading.py")
    finally:
        helper.write_text(original)
        added.unlink(missing_ok=True)


def test_nested_model_forms_create_redisplay_and_update_subscriptions(generated_store):
    _, run = generated_store
    run(script="nested_subscriptions.py")
