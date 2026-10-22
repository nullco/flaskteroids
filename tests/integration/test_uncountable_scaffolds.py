from tests.assertions import assert_pytest_passed


def test_generated_uncountable_scaffolds_render_and_persist(generated_uncountables):
    root, run = generated_uncountables
    report = root / "test.xml"
    run("test", "-q", "--junitxml", str(report))
    assert_pytest_passed(report)
