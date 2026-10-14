import os
import subprocess
import sys
from pathlib import Path

from flaskteroids.cli.flaskteroids import cli

GENERATED_TESTS = """import pytest
from flaskteroids.testing.context import current_response
from test.test_helper import IntegrationTest, delete, get, patch, post
from app.models.post import Post


class ResponsesTest(IntegrationTest):
    @pytest.mark.parametrize("suffix", ["", ".json"])
    @pytest.mark.parametrize("operation", ["create", "update"])
    def test_validation_failure(self, suffix, operation):
        headers = {"Accept": "application/json"} if not suffix else {}
        record = Post.create(title="Existing") if operation == "update" else None
        count = Post.count()
        url = f"/posts/{record.id}{suffix}/" if record else f"/posts{suffix}/"
        send = patch if record else post
        send(url, params={"post": {"title": ""}}, headers=headers)

        self.assert_response(422)
        response = current_response()
        assert response.mimetype == "application/json"
        assert response.get_json() == ["Field title is blank"]
        assert Post.count() == count
        if record:
            assert Post.find(record.id).title == "Existing"

    @pytest.mark.parametrize("suffix", ["", ".json"])
    def test_empty_index(self, suffix):
        headers = {"Accept": "application/json"} if not suffix else {}
        get(f"/posts{suffix}/", headers=headers)

        self.assert_response(200)
        assert current_response().get_json() == []

    @pytest.mark.parametrize("suffix", ["", ".json"])
    def test_json_create_and_update(self, suffix):
        headers = {"Accept": "application/json"} if not suffix else {}
        post(f"/posts{suffix}/", params={"post": {"title": "First"}}, headers=headers)

        self.assert_response(200)
        record = Post.last()
        data = current_response().get_json()
        assert (data["id"], data["title"]) == (record.id, "First")
        patch(f"/posts/{record.id}{suffix}/", params={"post": {"title": "Second"}}, headers=headers)

        self.assert_response(200)
        data = current_response().get_json()
        assert (data["id"], data["title"]) == (record.id, "Second")

    @pytest.mark.parametrize("suffix", ["", ".json"])
    def test_partial_update_preserves_omitted_attributes(self, suffix):
        headers = {"Accept": "application/json"} if not suffix else {}
        record = Post.create(title="Existing", completed=False)
        patch(
            f"/posts/{record.id}{suffix}/",
            params={"post": {"completed": True, "id": record.id + 1000}},
            headers=headers,
        )

        self.assert_response(200)
        data = current_response().get_json()
        assert (data["id"], data["title"], data["completed"]) == (
            record.id, "Existing", True
        )
        record.reload()
        assert record.title == "Existing"
        assert record.completed is True

    def test_json_destroy(self):
        record = Post.create(title="Existing")
        delete(f"/posts/{record.id}.json/")

        self.assert_response(204)
        assert current_response().data == b""
        assert Post.count() == 0

    @pytest.mark.parametrize("operation", ["create", "update"])
    def test_html_validation_failure(self, operation):
        record = Post.create(title="Existing") if operation == "update" else None
        url = f"/posts/{record.id}/" if record else "/posts/"
        send = patch if record else post
        send(url, params={"post": {"title": ""}})

        self.assert_response(422)
        assert current_response().mimetype == "text/html"
        assert "<form " in current_response().text
"""


def test_generated_scaffold_json_and_html_responses(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cli.main(args=["new", "weblog", "--skip-install"], standalone_mode=False)
    root = tmp_path / "weblog"
    environment = os.environ | {
        "PYTHONPATH": str(Path(__file__).parents[4]),
        "FLASK_ENV": "test",
    }

    def run(*args):
        result = subprocess.run(
            [sys.executable, "-m", "flask", *args],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result

    run("generate", "scaffold", "Post", "title:string", "completed:boolean")
    (root / "app/models/post.py").write_text(
        "from app.models.application_model import ApplicationModel\n"
        "from flaskteroids.model import validates\n"
        "from flaskteroids.rules import rules\n\n"
        '@rules(validates("title", presence=True))\n'
        "class Post(ApplicationModel):\n"
        "    pass\n"
    )
    (root / "test/controllers/responses_test.py").write_text(GENERATED_TESTS)

    result = run("test", "-q", "test/controllers")

    assert "21 passed" in result.stdout
