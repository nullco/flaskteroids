from pathlib import Path

import click


@click.group("agent-skills")
def agent_skills():
    """Locate version-matched agent skills.

    Matches the installed Flaskteroids version. Use the application's Python
    environment. No running app is required.
    """


@agent_skills.command("path")
def skills_path():
    """Print the absolute agent skills path.

    Outputs only the installed skills directory path.

    Read using-flaskteroids/SKILL.md inside this directory.

    \b
    Example:
      flaskteroids agent-skills path
    """
    click.echo(Path(__file__).resolve().parents[1] / ".agents" / "skills")
