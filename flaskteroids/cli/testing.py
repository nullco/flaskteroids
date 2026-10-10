import os

import click


@click.command("test", context_settings={"ignore_unknown_options": True})
@click.argument("pytest_args", nargs=-1, type=click.UNPROCESSED)
def test(pytest_args):
    """Run the application's test suite, excluding system tests."""
    _run_tests(("-m", "not system", *pytest_args))


@click.command("test:system", context_settings={"ignore_unknown_options": True})
@click.argument("pytest_args", nargs=-1, type=click.UNPROCESSED)
def test_system(pytest_args):
    """Run browser system tests."""
    _run_tests(("-m", "system", *pytest_args))


def _run_tests(pytest_args):
    import pytest

    previous_environment = os.environ.get("FLASKTEROIDS_ENV")
    os.environ["FLASKTEROIDS_ENV"] = "test"
    try:
        exit_code = pytest.main(list(pytest_args))
    finally:
        if previous_environment is None:
            os.environ.pop("FLASKTEROIDS_ENV", None)
        else:
            os.environ["FLASKTEROIDS_ENV"] = previous_environment
    raise SystemExit(exit_code)
