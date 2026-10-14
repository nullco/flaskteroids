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
    ab = mocker.patch(
        "flaskteroids.cli.generators.authentication.generator.ArtifactsBuilder"
    )
    instance = mocker.Mock()
    ab.return_value = instance
    return instance


@pytest.fixture
def template(mocker):
    t = mocker.patch("flaskteroids.cli.generators.authentication.generator.template")
    t.return_value = "template_content"
    return t


class TestAuthenticationGenerator:
    @pytest.mark.usefixtures("migrations", "template")
    def test_generate_adds_model_files(self, artifacts_builder, mocker):
        generate()
        artifacts_builder.file.assert_has_calls(
            [
                mocker.call.file("app/models/session.py", "template_content"),
                mocker.call.file("app/models/user.py", "template_content"),
            ],
            any_order=False,
        )

    @pytest.mark.usefixtures("migrations", "template")
    def test_generate_adds_view_files(self, artifacts_builder, mocker):
        generate()
        artifacts_builder.file.assert_has_calls(
            [
                mocker.call.file("app/views/sessions/new.html", "template_content"),
                mocker.call.file("app/views/passwords/new.html", "template_content"),
                mocker.call.file("app/views/passwords/edit.html", "template_content"),
                mocker.call.file(
                    "app/views/passwords_mailer/reset.html", "template_content"
                ),
                mocker.call.file(
                    "app/views/passwords_mailer/reset.txt", "template_content"
                ),
            ],
            any_order=False,
        )

    @pytest.mark.usefixtures("migrations", "template")
    def test_generate_adds_controller_files(self, artifacts_builder, mocker):
        generate()
        artifacts_builder.file.assert_has_calls(
            [
                mocker.call.file(
                    "app/controllers/concerns/authentication.py", "template_content"
                ),
                mocker.call.file(
                    "app/controllers/sessions_controller.py", "template_content"
                ),
                mocker.call.file(
                    "app/controllers/passwords_controller.py", "template_content"
                ),
            ],
            any_order=False,
        )

    @pytest.mark.usefixtures("migrations", "template")
    def test_generate_adds_mailer_file(self, artifacts_builder):
        generate()
        artifacts_builder.file.assert_any_call(
            "app/mailers/passwords_mailer.py", "template_content"
        )

    @pytest.mark.usefixtures("migrations", "template")
    def test_generate_adds_tests(self, artifacts_builder, mocker):
        generate()
        for path in [
            "test/models/user_test.py",
            "test/models/session_test.py",
            "test/controllers/sessions_controller_test.py",
            "test/controllers/passwords_controller_test.py",
        ]:
            artifacts_builder.file.assert_any_call(path, mocker.ANY)

    @pytest.mark.usefixtures("migrations", "template")
    def test_generate_modifies_application_controller(self, artifacts_builder, mocker):
        generate()
        artifacts_builder.modify_py_file.assert_has_calls(
            [
                mocker.call.modify_py_file(
                    "app/controllers/application_controller.py", mocker.ANY
                ),
                mocker.call.modify_py_file(
                    "app/controllers/application_controller.py", mocker.ANY
                ),
            ]
        )

    @pytest.mark.usefixtures("migrations", "template")
    def test_generate_modifies_routes(self, artifacts_builder, mocker):
        generate()
        artifacts_builder.modify_py_file.assert_any_call("config/routes.py", mocker.ANY)

    @pytest.mark.usefixtures("artifacts_builder", "template")
    def test_generate_creates_migrations(self, migrations, mocker):
        generate()
        migrations.generate.assert_has_calls(
            [
                mocker.call.generate(
                    "CreateUsers", ["email_address:str!", "password_digest:str!"]
                ),
                mocker.call.generate(
                    "CreateSessions",
                    ["user:references", "ip_address:str", "user_agent:str"],
                ),
            ]
        )

    @pytest.mark.usefixtures("artifacts_builder", "template")
    def test_generate_creates_expected_tables(self, mocker):
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
        user_id = next(
            column for column in tables[1].columns if column.name == "user_id"
        )
        assert [fk.target_fullname for fk in user_id.foreign_keys] == ["users.id"]
