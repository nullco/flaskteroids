import os

import click


@click.command("test", context_settings={"ignore_unknown_options": True})
@click.argument("pytest_args", nargs=-1, type=click.UNPROCESSED)
def test(pytest_args):
    """Run tests excluding browser tests.

    Run from the application root. Testing dependencies are included with
    Flaskteroids. Uses the test environment and prepares its database. Pass
    test paths and pytest options as PYTEST_ARGS. Returns pytest's exit code.

    \b
    Examples:
      flask test
      flask test test/models/post_test.py -q
      flask test -n auto
      flask test -- --help
    """
    _run_tests(("-m", "not system", *pytest_args))


@click.command("test:system", context_settings={"ignore_unknown_options": True})
@click.argument("pytest_args", nargs=-1, type=click.UNPROCESSED)
def test_system(pytest_args):
    """Run browser system tests.

    Run from the application root. Testing dependencies are included with
    Flaskteroids. Uses the test environment and prepares its database. Install
    the browser first with playwright install chromium. Pass test paths and
    pytest options as PYTEST_ARGS. Returns pytest's exit code.

    \b
    Examples:
      flask test:system
      flask test:system test/system/posts_test.py -q
      flask test:system -- --help
    """
    _run_tests(("-m", "system", *pytest_args))


def _run_tests(pytest_args):
    import pytest

    previous_environment = os.environ.get("FLASK_ENV")
    os.environ["FLASK_ENV"] = "test"
    try:
        exit_code = pytest.main(list(pytest_args))
    finally:
        if previous_environment is None:
            os.environ.pop("FLASK_ENV", None)
        else:
            os.environ["FLASK_ENV"] = previous_environment
    raise SystemExit(exit_code)
