from pathlib import Path

import click

from flaskteroids.assets import OUTPUT_PATH, SOURCE_PATH, AssetError, AssetPipeline
from flaskteroids.cli.output import status


@click.command(
    "assets:precompile", short_help="Precompile fingerprinted assets without app boot."
)
@click.option(
    "--root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    help="Application root; defaults to the current directory.",
)
@click.option(
    "--source",
    default=SOURCE_PATH,
    show_default=True,
    help="Source directory inside root.",
)
@click.option("--output", default=OUTPUT_PATH, show_default=True)
def precompile(root, source, output):
    """Precompile fingerprinted assets without booting the application.

    Copies stylesheets/images and writes a manifest for production. Does not
    need a database, credentials, or application initializers. No bundling or
    Sass compilation is performed. Relative CSS URLs/imports are fingerprinted.
    Custom source/output options must match config.assets in the application.

    \b
    Examples:
      bin/flask assets:precompile
      flaskteroids assets:precompile --root /path/to/my_app
    """
    try:
        pipeline = AssetPipeline(root, source_path=source, output_path=output)
        manifest = pipeline.precompile()
    except (AssetError, OSError) as error:
        raise click.ClickException(f"Asset precompilation failed: {error}") from error
    status("compile", f"{len(manifest)} assets into {pipeline.output}")
