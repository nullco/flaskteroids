import shutil
from pathlib import Path

import pytest

from tests.assertions import assert_pytest_passed
from tests.generated_application import cleanup_database


@pytest.fixture(scope="module")
def nested_application(generated_app_factory):
    root, run = generated_app_factory("nested_forms")
    run(
        commands=[
            ("generate", "scaffold", "Parent", "name:string"),
            (
                "generate",
                "model",
                "Child",
                "parent:references",
                "name:string",
                "quantity:integer",
            ),
        ]
    )
    source = Path(__file__).parents[1] / "integration/application/nested"
    for path in source.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            relative = path.relative_to(source)
            if relative == Path("test/controllers/contracts.py"):
                relative = Path("test/controllers/nested_contract_test.py")
            elif relative == Path("test/system/browser.py"):
                relative = Path("test/system/nested_test.py")
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
    run("db:prepare")
    try:
        yield root, run
    finally:
        cleanup_database(root, run)


def test_nested_json_and_parameter_contracts_in_a_generated_application(
    nested_application,
):
    root, run = nested_application
    report = root / "nested-requests.xml"
    run(
        "test",
        "-q",
        "--junitxml",
        str(report),
        "test/controllers/nested_contract_test.py",
    )
    assert_pytest_passed(report)


@pytest.mark.system
def test_nested_forms_in_a_generated_application(nested_application):
    root, run = nested_application
    report = root / "nested-browser.xml"
    run("test:system", "-q", "--junitxml", str(report), "test/system/nested_test.py")
    assert_pytest_passed(report)
