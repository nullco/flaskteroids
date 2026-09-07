from pathlib import Path
import click
import yaml
from flask import current_app
from flask.cli import with_appcontext
from flaskteroids.credentials import Credentials, encrypt, generate_key


@click.command("credentials:show")
@click.option("--environment")
@with_appcontext
def show(environment):
    """Show decrypted credentials."""
    store = _credentials(environment)
    click.echo(yaml.safe_dump(store.to_dict(), sort_keys=False), nl=False)


@click.command("credentials:edit")
@click.option("--environment")
@with_appcontext
def edit(environment):
    """Edit encrypted credentials."""
    store = _credentials(environment)
    key = store.key()
    if not key:
        key = generate_key()
        store.key_path.parent.mkdir(parents=True, exist_ok=True)
        store.key_path.write_text(f"{key}\n")
        click.echo(f"Adding {store.key_path} to store the encryption key.")

    if store.content_path.exists():
        contents = yaml.safe_dump(store.to_dict(), sort_keys=False)
    else:
        contents = "{}\n"
    edited = click.edit(contents, extension=".yml")
    if edited is None:
        click.echo("Credentials were not changed.")
        return

    data = yaml.safe_load(edited) or {}
    if not isinstance(data, dict):
        raise click.ClickException("Credentials must contain a YAML mapping.")
    store.content_path.parent.mkdir(parents=True, exist_ok=True)
    plaintext = yaml.safe_dump(data, sort_keys=False)
    store.content_path.write_text(encrypt(plaintext, key))
    click.echo(f"Encrypted and saved {store.content_path}.")


def _credentials(environment):
    if not environment:
        return current_app.credentials
    return Credentials(
        Path(current_app.project_root),
        environment,
        environment_specific=True,
    )
