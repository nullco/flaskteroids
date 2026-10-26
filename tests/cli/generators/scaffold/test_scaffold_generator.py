import pytest

from flaskteroids.cli.generators.scaffold.generator import generate


@pytest.fixture
def artifacts_builder(mocker):
    mock_builder = mocker.patch(
        "flaskteroids.cli.generators.scaffold.generator.ArtifactsBuilder"
    )
    mock_ab = mocker.Mock()
    mock_builder.return_value = mock_ab
    return mock_ab


@pytest.fixture
def model(mocker):
    return mocker.patch("flaskteroids.cli.generators.scaffold.generator.model")


@pytest.mark.usefixtures("model")
class TestScaffoldGenerator:
    def test_generate_creates_scaffold_artifacts(
        self, artifacts_builder, model, mocker
    ):
        generate("User", ["name:str"])

        expected_files = [
            "app/controllers/users_controller.py",
            "app/views/users/index.html",
            "app/views/users/new.html",
            "app/views/users/edit.html",
            "app/views/users/show.html",
            "app/views/users/_form.html",
            "app/views/users/_user.html",
            "test/controllers/users_controller_test.py",
            "test/fixtures/users.yml",
            "test/system/users_test.py",
        ]
        for file_path in expected_files:
            artifacts_builder.file.assert_any_call(file_path, mocker.ANY)
        artifacts_builder.modify_py_file.assert_called_once_with(
            "config/routes.py", mocker.ANY
        )
        model.generate.assert_called_once_with("User", ["name:str"])

    def test_generate_uses_fixed_upload_allowlist(self, artifacts_builder):
        generate("User", ["name:str", "avatar:attachment", "documents:attachments"])
        controller = next(
            call.args[1]
            for call in artifacts_builder.file.call_args_list
            if call.args[0] == "app/controllers/users_controller.py"
        )

        assert "permitted.append('avatar')" in controller
        assert "permitted.append(('documents', []))" in controller
        assert "self.params.expect(user=permitted)" in controller
