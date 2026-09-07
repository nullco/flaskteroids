from flaskteroids.credentials import Credentials


def test_credentials_show(cli_runner):
    result = cli_runner.invoke(args="credentials:show")

    assert result.exit_code == 0
    assert result.output == "{}\n"


def test_credentials_edit_for_environment(app, cli_runner, mocker, tmp_path):
    app.project_root = tmp_path
    mocker.patch(
        "flaskteroids.cli.credentials.click.edit",
        return_value="api_key: secret\n",
    )

    result = cli_runner.invoke(args=["credentials:edit", "--environment", "production"])

    assert result.exit_code == 0
    credentials = Credentials(tmp_path, "production")
    assert credentials.api_key == "secret"
    assert credentials.content_path == (
        tmp_path / "config" / "credentials" / "production.yml.enc"
    )
    assert credentials.key_path == (
        tmp_path / "config" / "credentials" / "production.key"
    )
