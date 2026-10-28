import shutil
from pathlib import Path

import pytest

from tests.assertions import assert_pytest_passed
from tests.generated_application import cleanup_database


@pytest.fixture(scope="module")
def restock_store(generated_app_factory):
    root, run = generated_app_factory("restock")
    run(
        commands=[
            ("db:create",),
            (
                "generate",
                "scaffold",
                "Product",
                "name:string",
                "inventory_count:integer",
            ),
            (
                "generate",
                "model",
                "Subscriber",
                "product:references",
                "email:string",
                "unsubscribe_token:string",
            ),
            ("generate", "authentication"),
            ("generate", "mailer", "Product", "in_stock"),
            ("attachments:install",),
        ]
    )
    source = Path(__file__).parent / "application/restock"
    for path in source.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            destination = root / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
    shutil.copyfile(
        source / "model_assigns_contracts.py",
        root / "test/mailers/model_assigns_test.py",
    )
    run("db:prepare")
    try:
        yield run
    finally:
        cleanup_database(root, run)


def test_getting_started_subscriptions_and_restock_delivery(restock_store):
    restock_store(script="restock_notifications.py")


def test_transactional_mailer_tests_render_model_assigns(restock_store, tmp_path):
    report = tmp_path / "mail-tests.xml"
    restock_store(
        "test", "-q", "--junitxml", str(report), "test/mailers/model_assigns_test.py"
    )
    assert_pytest_passed(report)


def test_model_assigns_reload_in_a_fresh_mail_worker(restock_store, tmp_path):
    payload = str(tmp_path / "model-mail.json")
    restock_store("enqueue", payload, script="model_mailer_assigns.py")
    restock_store("deliver", payload, script="model_mailer_assigns.py")
