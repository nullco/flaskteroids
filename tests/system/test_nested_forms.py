import pytest

from tests.assertions import assert_pytest_passed

pytestmark = pytest.mark.system


def test_nested_forms_in_a_generated_application(generated_nested_forms):
    root, run = generated_nested_forms
    report = root / "nested-browser.xml"
    run("test:system", "-q", "--junitxml", str(report), "test/system/nested_test.py")
    assert_pytest_passed(report)
