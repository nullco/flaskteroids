import pytest

from flaskteroids.cli.generators.controller.generator import generate


@pytest.fixture
def artifacts_builder(mocker):
    return mocker.patch(
        "flaskteroids.cli.generators.controller.generator.ArtifactsBuilder"
    ).return_value


def test_generate_creates_controller_files(artifacts_builder):
    generate("TestController", ["index", "show"])

    assert {call.args[0] for call in artifacts_builder.file.call_args_list} == {
        "app/controllers/test_controller_controller.py",
        "app/helpers/test_controller_helper.py",
        "test/controllers/test_controller_controller_test.py",
        "app/views/test_controller/index.html",
        "app/views/test_controller/show.html",
    }
    artifacts_builder.dir.assert_called_once_with("app/views/test_controller/")


def test_generate_adds_routes_by_default(artifacts_builder, mocker):
    generate("TestController", ["index"])
    artifacts_builder.modify_py_file.assert_called_once_with(
        "config/routes.py", mocker.ANY
    )


def test_generate_skips_routes_when_specified(artifacts_builder):
    generate("TestController", ["index"], skip_routes=True)
    artifacts_builder.modify_py_file.assert_not_called()
