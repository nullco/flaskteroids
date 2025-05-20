import os
import textwrap
import click
from pathlib import Path


class ArtifactsBuilder:

    def __init__(self, base_path: str):
        self._base_path = base_path

    def _join(self, name):
        if not name:
            return Path(self._base_path)
        return Path(self._base_path, name)

    def dir(self, name=None):
        os.makedirs(self._join(name), exist_ok=True)
        click.echo(f"    create  {name}")

    def file(self, name, contents=None):
        file_path = self._join(name)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch(exist_ok=True)
        if contents:
            file_path.write_text(self._clean(contents))
        click.echo(f"    create  {name}")

    def _clean(self, txt: str):
        return textwrap.dedent(txt).lstrip()
