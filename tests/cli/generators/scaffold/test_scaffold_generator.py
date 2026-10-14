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


@pytest.mark.usefixtures("app_ctx", "model", "artifacts_builder")
class TestScaffoldGenerator:
    def test_generate_creates_controller_file(self, artifacts_builder, mocker):
        generate("User", ["name:str"])
        artifacts_builder.file.assert_any_call(
            "app/controllers/users_controller.py", mocker.ANY
        )

    def test_generate_uses_fixed_upload_allowlist(self, artifacts_builder):
        generate("User", ["name:str", "avatar:attachment", "documents:attachments"])
        controller = next(
            call.args[1]
            for call in artifacts_builder.file.call_args_list
            if call.args[0] == "app/controllers/users_controller.py"
        )

        assert "permitted.append('avatar')" in controller
        assert "permitted.append(('documents', []))" in controller
        assert "in params.get(" not in controller

    def test_generate_creates_view_files(self, artifacts_builder, mocker):
        generate("User", ["name:str"])
        expected_files = [
            "app/views/users/index.html",
            "app/views/users/new.html",
            "app/views/users/edit.html",
            "app/views/users/show.html",
            "app/views/users/_form.html",
            "app/views/users/_user.html",
        ]
        for file_path in expected_files:
            artifacts_builder.file.assert_any_call(file_path, mocker.ANY)

    def test_generate_creates_tests_and_fixtures(self, artifacts_builder, mocker):
        generate("User", ["name:str"])
        artifacts_builder.file.assert_any_call(
            "test/controllers/users_controller_test.py", mocker.ANY
        )
        artifacts_builder.file.assert_any_call("test/fixtures/users.yml", mocker.ANY)
        artifacts_builder.file.assert_any_call("test/system/users_test.py", mocker.ANY)

    def test_generate_modifies_routes(self, artifacts_builder, mocker):
        generate("User", ["name:str"])
        artifacts_builder.modify_py_file.assert_called_once_with(
            "config/routes.py", mocker.ANY
        )

    @pytest.mark.usefixtures("artifacts_builder")
    def test_generate_calls_model_generate(self, model):
        generate("User", ["name:str"])
        model.generate.assert_called_once_with("User", ["name:str"])
