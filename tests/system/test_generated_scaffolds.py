from tests.assertions import assert_pytest_passed


def test_generated_scaffold_system_tests_pass(generated_scaffolds):
    root, run = generated_scaffolds
    report = root / "test-system.xml"
    run("test:system", "-q", "--junitxml", str(report))
    assert_pytest_passed(report)
