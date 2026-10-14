import ast

import pytest

from flaskteroids.cli.generators.controller.generator import generate as controller
from flaskteroids.cli.generators.mailer.generator import generate as mailer
from flaskteroids.cli.generators.model.generator import generate as model


@pytest.mark.parametrize("actions", [[], ["index"], ["index", "show"]])
def test_action_variants_compile_and_preserve_jinja(tmp_path, monkeypatch, actions):
    monkeypatch.chdir(tmp_path)
    controller("Posts", actions, skip_routes=True)
    mailer("notifications", actions)
    for path in tmp_path.rglob("*.py"):
        ast.parse(path.read_text())
    for action in actions:
        assert (
            f"def {action}(self):"
            in (tmp_path / "app/controllers/posts_controller.py").read_text()
        )
        assert (
            "{{ greeting }}"
            in (tmp_path / f"app/views/notifications_mailer/{action}.html").read_text()
        )
        assert (
            "{{ greeting }}"
            in (tmp_path / f"app/views/notifications_mailer/{action}.txt").read_text()
        )


@pytest.mark.parametrize(
    "attachments",
    [[], ["avatar:attachment"], ["avatar:attachment", "photos:attachments"]],
)
def test_attachment_variants_compile(tmp_path, monkeypatch, mocker, attachments):
    monkeypatch.chdir(tmp_path)
    mocker.patch("flaskteroids.cli.generators.model.generator.migrations.generate")
    model("Post", ["title:string", *attachments])
    source = (tmp_path / "app/models/post.py").read_text()
    ast.parse(source)
    if attachments:
        assert "has_one_attached('avatar')" in source
    if len(attachments) == 2:
        assert "has_many_attached('photos')" in source
