import pytest
from alembic.operations import ops

from flaskteroids.cli.generators.authentication.generator import generate


@pytest.fixture
def migrations(mocker):
    return mocker.patch(
        "flaskteroids.cli.generators.authentication.generator.migrations"
    )


@pytest.fixture
def artifacts_builder(mocker):
    return mocker.patch(
        "flaskteroids.cli.generators.authentication.generator.ArtifactsBuilder"
    ).return_value


@pytest.mark.usefixtures("migrations")
def test_generate_creates_authentication_files_and_updates_application(
    artifacts_builder, mocker
):
    generate()

    assert {call.args[0] for call in artifacts_builder.file.call_args_list} == {
        "app/models/session.py",
        "app/models/user.py",
        "app/views/sessions/new.html",
        "app/views/passwords/new.html",
        "app/views/passwords/edit.html",
        "app/views/passwords_mailer/reset.html",
        "app/views/passwords_mailer/reset.txt",
        "app/controllers/concerns/authentication.py",
        "app/controllers/sessions_controller.py",
        "app/controllers/passwords_controller.py",
        "app/mailers/passwords_mailer.py",
        "test/models/user_test.py",
        "test/models/session_test.py",
        "test/controllers/sessions_controller_test.py",
        "test/controllers/passwords_controller_test.py",
    }
    artifacts_builder.modify_py_file.assert_has_calls(
        [
            mocker.call("app/controllers/application_controller.py", mocker.ANY),
            mocker.call("app/controllers/application_controller.py", mocker.ANY),
            mocker.call("config/routes.py", mocker.ANY),
        ]
    )


@pytest.mark.usefixtures("artifacts_builder")
def test_generate_creates_migrations(migrations, mocker):
    generate()
    migrations.generate.assert_has_calls(
        [
            mocker.call("CreateUsers", ["email_address:str!", "password_digest:str!"]),
            mocker.call(
                "CreateSessions",
                ["user:references", "ip_address:str", "user_agent:str"],
            ),
        ]
    )


@pytest.mark.usefixtures("artifacts_builder")
def test_generate_creates_expected_tables(mocker):
    mocker.patch("flaskteroids.cli.generators.migrations.generator.get_config")
    revision = mocker.patch(
        "flaskteroids.cli.generators.migrations.generator.command.revision"
    )

    generate()

    scripts = []
    for call in revision.call_args_list:
        script = ops.MigrationScript(None, ops.UpgradeOps([]), ops.DowngradeOps([]))
        call.kwargs["process_revision_directives"](None, None, [script])
        scripts.append(script)

    tables = [script.upgrade_ops.ops[0] for script in scripts]
    assert [table.table_name for table in tables] == ["users", "sessions"]
    assert [script.downgrade_ops.ops[0].table_name for script in scripts] == [
        "users",
        "sessions",
    ]
    user_id = next(column for column in tables[1].columns if column.name == "user_id")
    assert [fk.target_fullname for fk in user_id.foreign_keys] == ["users.id"]
