import ast
import os
import subprocess
import sys
import textwrap
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
        if str(name).startswith("bin/") or str(name).endswith(".sh"):
            try:
                file_path.chmod(file_path.stat().st_mode | 0o111)
            except OSError as error:
                raise ArtifactsBuilderException(
                    f"Cannot make script {name} executable: {error}"
                ) from error
        self._notify(f"    create  {name}")

    def modify_py_file(self, name, contents):
        with open(self._join(name), "r") as source:
            tree = ast.parse(source.read())
        tree = contents().visit(tree)
        with open(self._join(name), "w") as target:
            target.write(ast.unparse(tree))
        self._notify(f"    modify  {name}")

    def run(self, cmd: str) -> None:
        self._execute(cmd.split(), cmd)

    def python_run(self, cmd: str) -> None:
        self._execute([sys.executable, "-m", *cmd.split()], cmd)

    def _execute(self, argv: list[str], cmd: str) -> None:
        # Failed commands use the framework's status/stderr diagnostics below.
        res = subprocess.run(  # noqa: PLW1510
            argv, cwd=self._base_path, capture_output=True, text=True
        )
        if res.returncode != 0:
            raise ArtifactsBuilderException(
                f"command {cmd} returned {res.returncode}:\n{res.stderr}"
            )
        self._notify(f"    run  {cmd}")

    def _clean(self, txt: str):
        return textwrap.dedent(txt).lstrip()
