import shutil
from pathlib import Path

from tests.assertions import assert_pytest_passed
from tests.generated_application import cleanup_database


def test_membership_workflows_in_a_generated_application(generated_app_factory):
    root, run = generated_app_factory("memberships")
    run(
        commands=[
            ("generate", "model", "Organization", "name:string"),
            ("generate", "model", "Person", "name:string"),
            (
                "generate",
                "model",
                "Membership",
                "organization:references",
                "person:references",
                "role:string",
            ),
        ]
    )
    source = Path(__file__).parent / "application/memberships"
    for path in source.rglob("*.py"):
        destination = root / path.relative_to(source)
        if path.name == "contracts.py":
            destination = destination.with_name("membership_workflow_test.py")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    run("db:prepare")
    try:
        report = root / "memberships.xml"
        run(
            "test",
            "-q",
            "--junitxml",
            str(report),
            "test/models/membership_workflow_test.py",
        )
        assert_pytest_passed(report)
    finally:
        cleanup_database(root, run)
