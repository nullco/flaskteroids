import shlex

import pytest
from click.testing import CliRunner

from flaskteroids.cli.flaskteroids import cli
from flaskteroids.cli.generators.commands import generate
from flaskteroids.cli.generators.fields import fields

STANDALONE_HELP = {
    (): ["flask --help", "application root"],
    ("new",): [
        "APP_NAME",
        "--skip-install",
        "bin/setup",
        "Installs dependencies",
        "overwritten",
        "flaskteroids new my_app",
    ],
    ("assets:precompile",): [
        "--root",
        "--source",
        "--output",
        "without booting",
        "bin/flask assets:precompile",
    ],
    ("agent-skills",): ["No running app is required", "installed Flaskteroids version"],
    ("agent-skills", "path"): [
        "absolute agent skills path",
        "using-flaskteroids/SKILL.md",
    ],
}

APPLICATION_HELP = {
    ("assets:precompile",): ["--root", "fingerprinted", "database", "Examples"],
    ("generate",): ["alias: g", "overwritten", "flask db:migrate"],
    ("g",): ["alias: g", "overwritten"],
    ("generate", "migration"): [
        "NAME [FIELDS]...",
        "Create<TABLE>",
        "Drop<TABLE>",
        "Add<X>To<TABLE>",
        "Remove<X>From<TABLE>",
        "manual rollback code",
    ],
    ("generate", "model"): [
        "NAME [FIELDS]...",
        "singular CamelCase",
        "migration, and tests",
    ],
    ("generate", "controller"): [
        "NAME [ACTIONS]...",
        "without the Controller suffix",
        "--skip-routes",
        "GET route",
    ],
    ("generate", "mailer"): [
        "NAME [ACTIONS]...",
        "without the Mailer suffix",
        "HTML/text",
    ],
    ("generate", "scaffold"): [
        "NAME [FIELDS]...",
        "HTML CRUD",
        "fixtures",
        "browser test",
    ],
    ("generate", "resource"): [
        "NAME [FIELDS]...",
        "empty controller",
        "does not generate",
    ],
    ("generate", "authentication"): [
        "password reset",
        "overwritten",
        "Does not include user registration",
    ],
    ("attachments:install",): [
        "attachment tables migration",
        "flask db:init",
        "config/storage.yml",
        "flask db:migrate",
        "duplicate migrations",
    ],
    ("db:init",): ["db/migrate", "does not apply migrations", "absent or empty"],
    ("db:create",): ["selected database", "connectable", "no migrations required"],
    ("db:schema:dump",): [
        "db/schema.py",
        "without changing data",
        "initialization runs normally",
    ],
    ("db:migrate",): ["all pending", "current environment", "delete data"],
    ("db:prepare",): ["selected database", "DATABASE_URL", "fresh process"],
    ("db:rollback",): ["one database migration", "manual reversal code", "delete data"],
    ("credentials:show",): ["YAML", "--environment NAME", "plaintext secrets"],
    ("credentials:edit",): [
        "VISUAL or EDITOR",
        "--environment NAME",
        "Never commit key files",
    ],
    ("test",): [
        "PYTEST_ARGS",
        "test environment",
        "excluding browser",
        "pytest's exit code",
    ],
    ("test:system",): [
        "PYTEST_ARGS",
        "test environment",
        "playwright install chromium",
        "pytest's exit code",
    ],
}


@pytest.mark.parametrize(("args", "expected"), STANDALONE_HELP.items())
def test_standalone_command_help(args, expected):
    result = CliRunner().invoke(cli, [*args, "--help"])

    assert result.exit_code == 0
    output = " ".join(result.output.split())
    for text in expected:
        assert text in output


@pytest.mark.parametrize(("args", "expected"), APPLICATION_HELP.items())
def test_application_command_help(cli_runner, args, expected):
    result = cli_runner.invoke(args=[*args, "--help"])

    assert result.exit_code == 0
    output = " ".join(result.output.split())
    for text in expected:
        assert text in output
    assert "Example" in output


@pytest.mark.parametrize("args", [[], ["agent-skills"]])
def test_standalone_command_summaries_fit_terminal(args):
    result = CliRunner().invoke(cli, [*args, "--help"], terminal_width=80)

    assert result.exit_code == 0
    commands = result.output.partition("Commands:\n")[2]
    assert commands
    assert "..." not in commands
    assert all(len(line) <= 80 for line in commands.splitlines())


@pytest.mark.parametrize("args", [[], ["generate"], ["g"]])
def test_application_command_summaries_fit_terminal(cli_runner, args):
    result = cli_runner.invoke(args=[*args, "--help"], terminal_width=80)

    assert result.exit_code == 0
    commands = result.output.partition("Commands:\n")[2]
    assert commands
    assert "..." not in commands
    assert all(len(line) <= 80 for line in commands.splitlines())


def test_help_covers_all_registered_commands(app):
    assert set(cli.commands) == {args[0] for args in STANDALONE_HELP if args}
    assert set(cli.commands["agent-skills"].commands) == {"path"}
    assert set(app.cli.commands) == {args[0] for args in APPLICATION_HELP}
    assert set(generate.commands) == {
        args[1] for args in APPLICATION_HELP if len(args) == 2
    }


@pytest.mark.parametrize("command", ["migration", "model", "scaffold", "resource"])
def test_field_generator_help_lists_supported_syntax(cli_runner, command):
    result = cli_runner.invoke(args=["generate", command, "--help"])

    assert result.exit_code == 0
    output = " ".join(result.output.split())
    assert f"Types: {', '.join(fields)}." in output
    assert "name:TYPE! for NOT NULL" in output
    assert "user:references or user:belongs_to" in output
    assert "required foreign key" in output


@pytest.mark.parametrize(
    "command", ["migration", "model", "controller", "mailer", "scaffold", "resource"]
)
def test_generators_require_a_name(cli_runner, command):
    result = cli_runner.invoke(args=["generate", command])

    assert result.exit_code == 2
    assert "Missing argument 'NAME'" in result.output


@pytest.mark.parametrize(
    ("name", "module", "expected"),
    [
        (
            "migration",
            "migrations",
            [
                ("CreatePosts", ["title:string"]),
                ("AddPublishedToPosts", ["published:boolean!"]),
                ("RemoveTitleFromPosts", ["title:string"]),
                ("DropPosts", []),
            ],
        ),
        ("model", "model", [("Post", ["title:string", "user:references"])]),
        (
            "controller",
            "controller",
            [("Posts", ("index", "show"), False), ("Posts", ("index",), True)],
        ),
        ("mailer", "mailer", [("Notifications", ("welcome",))]),
        ("scaffold", "scaffold", [("Post", ["title:string", "content:text"])]),
        ("resource", "resource", [("Post", ["title:string"])]),
        ("authentication", "authentication", [()]),
    ],
)
def test_documented_generator_examples_dispatch(
    cli_runner, mocker, name, module, expected
):
    generator = mocker.patch(f"flaskteroids.cli.generators.commands.{module}.generate")
    help_result = cli_runner.invoke(args=["generate", name, "--help"])
    assert help_result.exit_code == 0
    generator.assert_not_called()
    examples = [
        shlex.split(line.strip())[1:]
        for line in help_result.output.splitlines()
        if line.strip().startswith(f"flask generate {name} ")
        or line.strip() == f"flask generate {name}"
    ]

    assert len(examples) == len(expected)
    for args in examples:
        result = cli_runner.invoke(args=args)
        assert result.exit_code == 0, result.output
    assert generator.call_args_list == [mocker.call(*args) for args in expected]


@pytest.mark.parametrize("command", ["test", "test:system"])
def test_documented_pytest_help_forwarding(cli_runner, mocker, command):
    pytest_main = mocker.patch("pytest.main", return_value=0)

    result = cli_runner.invoke(args=[command, "--", "--help"])

    assert result.exit_code == 0
    marker = "system" if command == "test:system" else "not system"
    pytest_main.assert_called_once_with(["-m", marker, "--help"])
