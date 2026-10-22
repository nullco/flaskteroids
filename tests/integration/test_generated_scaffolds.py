from tests.assertions import assert_pytest_passed


def test_generated_scaffolds_render_and_persist(generated_scaffolds):
    root, run = generated_scaffolds
    report = root / "test.xml"
    run("test", "-q", "--junitxml", str(report))
    assert_pytest_passed(report)
