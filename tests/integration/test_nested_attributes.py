from tests.assertions import assert_pytest_passed


def test_nested_json_and_parameter_contracts_in_a_generated_application(
    generated_nested_forms,
):
    root, run = generated_nested_forms
    report = root / "nested-requests.xml"
    run(
        "test",
        "-q",
        "--junitxml",
        str(report),
        "test/controllers/nested_contract_test.py",
    )
    assert_pytest_passed(report)
