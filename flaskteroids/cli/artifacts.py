import ast
import os
import textwrap
import subprocess
from pathlib import Path


class ArtifactsBuilderException(Exception):
    pass


class ArtifactsBuilder:

    def __init__(self, base_path: str, notify_fn=None):
        self._base_path = base_path
        self._notify = notify_fn or (lambda txt: None)

    def _join(self, name):
        if not name:
            return Path(self._base_path)
        return Path(self._base_path, name)

    def dir(self, name=None):
        os.makedirs(self._join(name), exist_ok=True)
        self._notify(f"    create  {name}")

    def file(self, name, contents=None):
        file_path = self._join(name)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch(exist_ok=True)
        if contents:
            file_path.write_text(self._clean(contents))
        self._notify(f"    create  {name}")

    def modify_py_file(self, name, contents):
        with open(self._join(name), "r") as source:
            tree = ast.parse(source.read())
        tree = contents().visit(tree)
        with open(self._join(name), "w") as target:
            target.write(ast.unparse(tree))
        self._notify(f"    modify  {name}")

    def run(self, cmd: str):
        res = subprocess.run(
            cmd.split(),
            cwd=self._base_path,
            capture_output=True,
            text=True
        )
        if res.returncode != 0:
            raise ArtifactsBuilderException(f'command {cmd} returned {res.returncode}:\n{res.stderr}')
        self._notify(f"    run  {cmd}")

    def _clean(self, txt: str):
        return textwrap.dedent(txt).lstrip()
