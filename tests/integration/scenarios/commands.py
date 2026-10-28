"""Run setup or cleanup commands without restarting Flask between each command."""

import json
import shlex
import sys

from click.testing import CliRunner
from flask.cli import cli

for arguments in json.loads(sys.argv[1]):
    print(f"$ flask {shlex.join(arguments)}", flush=True)
    result = CliRunner().invoke(cli, arguments)
    print(result.output, end="", flush=True)
    if result.exit_code:
        raise SystemExit(result.exit_code)
