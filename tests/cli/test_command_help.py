import re
import shlex

import pytest
from click.testing import CliRunner

from flaskteroids.cli.flaskteroids import cli
from flaskteroids.cli.generators.commands import generate
from flaskteroids.cli.generators.fields import fields

STANDALONE_HELP = {
    (): ["flask --help"],
    ("new",): ["APP_NAME", "--skip-install", "bin/setup"],
    ("assets:precompile",): ["--root", "--source", "--output"],
    ("agent-skills",): ["path"],
    ("agent-skills", "path"): [],
}

APPLICATION_HELP = {
    ("assets:precompile",): ["--root"],
    ("generate",): [],
    ("g",): [],
    ("generate", "migration"): [
        "NAME",
        "FIELDS",
        "Create<TABLE>",
        "Drop<TABLE>",
        "Add<X>To<TABLE>",
        "Remove<X>From<TABLE>",
    ],
    ("generate", "model"): ["NAME", "FIELDS"],
    ("generate", "controller"): ["NAME", "ACTIONS", "--skip-routes"],
    ("generate", "mailer"): ["NAME", "ACTIONS"],
    ("generate", "scaffold"): ["NAME", "FIELDS"],
    ("generate", "resource"): ["NAME", "FIELDS"],
    ("generate", "authentication"): [],
    ("attachments:install",): ["config/storage.yml"],
    ("rich_text:install",): ["db:migrate", "rich_texts", "--force"],
    ("db:encryption:init",): ["credentials:edit"],
    ("db:init",): ["db/migrate"],
    ("db:create",): [],
    ("db:schema:dump",): ["db/schema.py"],
    ("db:migrate",): [],
    ("db:prepare",): ["FLASKTEROIDS_DATABASE_URL"],
    ("db:rollback",): [],
    ("credentials:show",): ["--environment", "NAME"],
    ("credentials:edit",): ["--environment", "NAME"],
    ("test",): ["PYTEST_ARGS"],
    ("test:system",): ["PYTEST_ARGS"],
}


@pytest.mark.parametrize(("args", "expected"), STANDALONE_HELP.items())
def test_standalone_help_exposes_command_interface(args, expected):
    result = CliRunner().invoke(cli, [*args, "--help"])

    assert result.exit_code == 0
    output = " ".join(result.output.split())
    for text in expected:
        assert text in output


@pytest.mark.parametrize(("args", "expected"), APPLICATION_HELP.items())
def test_application_help_exposes_command_interface(cli_runner, args, expected):
    result = cli_runner.invoke(args=[*args, "--help"])

    assert result.exit_code == 0
    output = " ".join(result.output.split())
    for text in expected:
        assert text in output


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
    assert set(fields) <= set(re.findall(r"\b\w+\b", output))
    for syntax in ("name:TYPE!", "user:references", "user:belongs_to"):
        assert syntax in output


@pytest.mark.parametrize(
    "command", ["migration", "model", "controller", "mailer", "scaffold", "resource"]
)
def test_generators_require_a_name(cli_runner, command):
    result = cli_runner.invoke(args=["generate", command])

    assert result.exit_code == 2


@pytest.mark.parametrize(
    "args, module, expected",
    [
        (
            ["migration", "CreatePosts", "title:string"],
            "migrations",
            ("CreatePosts", ["title:string"]),
        ),
        (
            ["migration", "AddPublishedToPosts", "published:boolean!"],
            "migrations",
            ("AddPublishedToPosts", ["published:boolean!"]),
        ),
        (
            ["migration", "RemoveTitleFromPosts", "title:string"],
            "migrations",
            ("RemoveTitleFromPosts", ["title:string"]),
        ),
        (["migration", "DropPosts"], "migrations", ("DropPosts", [])),
        (
            ["model", "Post", "title:string", "user:references"],
            "model",
            ("Post", ["title:string", "user:references"]),
        ),
        (
            ["controller", "Posts", "index", "show"],
            "controller",
            ("Posts", ("index", "show"), False),
        ),
        (
            ["controller", "Posts", "index", "--skip-routes"],
            "controller",
            ("Posts", ("index",), True),
        ),
        (
            ["mailer", "Notifications", "welcome"],
            "mailer",
            ("Notifications", ("welcome",)),
        ),
        (
            ["scaffold", "Post", "title:string", "content:text"],
            "scaffold",
            ("Post", ["title:string", "content:text"]),
        ),
        (["resource", "Post", "title:string"], "resource", ("Post", ["title:string"])),
        (["authentication"], "authentication", ()),
    ],
)
def test_generator_commands_forward_arguments(
    cli_runner, mocker, args, module, expected
):
    generator = mocker.patch(f"flaskteroids.cli.generators.commands.{module}.generate")

    result = cli_runner.invoke(args=["generate", *args])

    assert result.exit_code == 0, result.output
    generator.assert_called_once_with(*expected)


@pytest.mark.parametrize(
    "name, module",
    [
        ["migration", "migrations"],
        ["model", "model"],
        ["controller", "controller"],
        ["mailer", "mailer"],
        ["scaffold", "scaffold"],
        ["resource", "resource"],
        ["authentication", "authentication"],
    ],
)
def test_documented_generator_examples_dispatch(cli_runner, mocker, name, module):
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

    assert examples
    for args in examples:
        generator.reset_mock()
        result = cli_runner.invoke(args=args)
        assert result.exit_code == 0, result.output
        generator.assert_called_once()


@pytest.mark.parametrize("command", ["test", "test:system"])
def test_test_commands_forward_documented_pytest_help_arguments(
    cli_runner, mocker, command
):
    pytest_main = mocker.patch("pytest.main", return_value=0)

    result = cli_runner.invoke(args=[command, "--", "--help"])

    assert result.exit_code == 0
    marker = "system" if command == "test:system" else "not system"
    pytest_main.assert_called_once_with(["-m", marker, "--help"])
