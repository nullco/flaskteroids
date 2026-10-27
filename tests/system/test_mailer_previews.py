import pytest


@pytest.mark.parametrize("options", [(), ("--api",)])
def test_generated_mailer_browser_switches_formats_and_sandboxes_html(
    generated_app_factory, options
):
    _, run = generated_app_factory("mailer_previews", *options)
    run("generate", "mailer", "Notices", "welcome")
    run("notices_mailer", "browser", script="mailer_previews.py")
