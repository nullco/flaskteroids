import ast

import yaml

from tests.assertions import assert_pytest_passed


def test_generated_api_application_passes_its_request_suite(generated_api):
    root, run = generated_api
    report = root / "api-tests.xml"

    run("test", "-q", "--junitxml", str(report))

    assert_pytest_passed(report)


def test_generated_api_mailer_previews_render_without_delivery(generated_api):
    _, run = generated_api
    run("notifications_mailer", script="mailer_previews.py")


def test_api_generators_omit_browser_artifacts(generated_api):
    root, _ = generated_api

    assert not (root / "app/assets").exists()
    assert not (root / "app/helpers").exists()
    assert not (root / "test/system").exists()
    assert not (root / "app/views/posts").exists()
    assert not (root / "app/views/status").exists()
    assert not (root / "app/views/layouts/application.html").exists()
    assert (root / "app/views/notifications_mailer/welcome.html").is_file()
    assert "assets:precompile" not in (root / "Dockerfile").read_text()
    workflow = yaml.safe_load((root / ".github/workflows/test.yml").read_text())
    commands = [step.get("run", "") for step in workflow["jobs"]["test"]["steps"]]
    assert "bin/flask test" in commands
    assert not any(
        "playwright" in command or "test:system" in command for command in commands
    )

    controller = ast.parse((root / "app/controllers/posts_controller.py").read_text())
    actions = {
        node.name
        for node in controller.body[-1].body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    }
    assert actions == {"index", "show", "create", "update", "destroy"}
    for path in root.rglob("*.py"):
        if ".venv" not in path.parts:
            ast.parse(path.read_text(), filename=str(path))
