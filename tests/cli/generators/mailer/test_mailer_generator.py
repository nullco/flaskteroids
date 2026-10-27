import pytest

from flaskteroids.cli.generators.mailer.generator import generate


@pytest.fixture
def artifacts_builder(mocker):
    return mocker.patch(
        "flaskteroids.cli.generators.mailer.generator.ArtifactsBuilder"
    ).return_value


def test_generate_creates_mailer_files(artifacts_builder):
    generate("test_mailer", ["welcome", "goodbye"])

    assert {call.args[0] for call in artifacts_builder.file.call_args_list} == {
        "app/mailers/test_mailer_mailer.py",
        "test/mailers/test_mailer_mailer_test.py",
        "test/mailers/previews/test_mailer_mailer_preview.py",
        "app/views/test_mailer_mailer/welcome.html",
        "app/views/test_mailer_mailer/welcome.txt",
        "app/views/test_mailer_mailer/goodbye.html",
        "app/views/test_mailer_mailer/goodbye.txt",
    }
    artifacts_builder.dir.assert_called_once_with("app/views/test_mailer_mailer/")
