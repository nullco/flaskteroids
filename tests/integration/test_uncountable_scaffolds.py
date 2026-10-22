import pytest

from tests.assertions import assert_pytest_passed


@pytest.fixture(scope="module")
def generated_uncountables(generated_app_factory):
    root, run = generated_app_factory("aquarium")
    run("db:create")
    for model in ("Fish", "Equipment"):
        run("generate", "scaffold", model, "name:string")
    run("db:prepare")
    try:
        yield root, run
    finally:
        for _ in ("Fish", "Equipment"):
            run("db:rollback")


@pytest.mark.parametrize("suite", ["test", "test:system"])
def test_generated_uncountable_scaffolds_render_and_persist(
    generated_uncountables, suite
):
    root, run = generated_uncountables
    report = root / f"{suite.replace(':', '-')}.xml"
    arguments = [suite, "-q", "--junitxml", str(report)]
    run(*arguments)
    assert_pytest_passed(report)
