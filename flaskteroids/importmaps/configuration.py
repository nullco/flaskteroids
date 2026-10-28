"""Conservative, AST-guided edits to application-owned pin declarations.

Configuration is ordinary Python. Commands only edit literal pin statements directly
inside register(); dynamic configurations remain supported at runtime, not rewritten.
"""

import ast
import json
import re
from dataclasses import dataclass

from flaskteroids.importmaps.errors import ImportmapError


@dataclass(frozen=True)
class PackagePin:
    name: str
    filename: str
    version: str | None


class PinFile:
    def __init__(self, path):
        self.path = path
        self.source = path.read_text(encoding="utf-8")
        self.lines = self.source.splitlines(keepends=True)
        tree = ast.parse(self.source, filename=str(path))
        functions = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "register"
        ]
        if len(functions) != 1 or len(functions[0].args.args) != 1:
            raise ImportmapError("Pin commands require def register(importmap)")
        self.register = functions[0]
        if self.register.lineno == self.register.body[0].lineno:
            raise ImportmapError("Pin commands require a multiline register(importmap)")
        first = self.register.body[0]
        self.indentation = self.lines[first.lineno - 1][: first.col_offset]
        parameter = self.register.args.args[0].arg
        self.declarations = {}
        direct_calls = set()
        for node in self.register.body:
            if not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and isinstance(node.value.func.value, ast.Name)
                and node.value.func.value.id == parameter
                and node.value.func.attr == "pin"
            ):
                continue
            call = node.value
            if (
                len(call.args) != 1
                or not isinstance(call.args[0], ast.Constant)
                or not isinstance(call.args[0].value, str)
                or any(keyword.arg is None for keyword in call.keywords)
                or self.lines[node.lineno - 1][: node.col_offset].strip()
                or self.trailing(node).lstrip().startswith(";")
            ):
                raise ImportmapError(
                    "Edit computed or compound pin declarations manually"
                )
            name = call.args[0].value
            if name in self.declarations:
                raise ImportmapError(
                    f"Edit duplicate pin declarations manually: {name}"
                )
            self.declarations[name] = node
            direct_calls.add(call)
        for node in ast.walk(self.register):
            if isinstance(node, (ast.Return, ast.Raise)) or (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == parameter
                and node.func.attr == "pin"
                and node not in direct_calls
            ):
                raise ImportmapError("Edit dynamic import-map configuration manually")

    def trailing(self, node):
        line = self.lines[node.end_lineno - 1].encode("utf-8")
        return line[node.end_col_offset :].decode("utf-8").strip()

    def filenames(self):
        filenames = {}
        for name, node in self.declarations.items():
            target = next(
                (
                    keyword.value
                    for keyword in node.value.keywords
                    if keyword.arg == "to"
                ),
                ast.Constant(f"{name}.js"),
            )
            if not isinstance(target, ast.Constant) or not isinstance(
                target.value, str
            ):
                raise ImportmapError(f"Edit computed package target manually: {name}")
            filenames[name] = target.value
        return filenames

    def packages(self):
        result = []
        filenames = self.filenames()
        for name, node in self.declarations.items():
            version = re.match(r"# @([^\s]+)", self.trailing(node))
            if version:
                result.append(PackagePin(name, filenames[name], version[1]))
        return tuple(result)

    def render_local_pins(self, pins):
        additions = [
            f"{self.indentation}{self.register.args.args[0].arg}.pin("
            f"{json.dumps(name)}, to={json.dumps(target)})\n"
            for name, target in pins.items()
            if name not in self.declarations
        ]
        if not additions:
            return self.source
        lines = list(self.lines)
        position = self.register.body[-1].end_lineno
        prefix = "" if lines[position - 1].endswith("\n") else "\n"
        lines.insert(position, prefix + "".join(additions))
        return "".join(lines)

    def render(self, packages=(), *, remove=(), preload=None):
        edits = []
        additions = []
        for package in packages:
            node = self.declarations.get(package.name)
            options = (
                {
                    keyword.arg: ast.unparse(keyword.value)
                    for keyword in node.value.keywords
                }
                if node
                else {}
            )
            options["to"] = json.dumps(package.filename)
            if preload is not None:
                options["preload"] = repr(preload)
            arguments = ", ".join(
                [
                    json.dumps(package.name),
                    *(f"{key}={value}" for key, value in options.items()),
                ]
            )
            comment = f"# @{package.version or 'unknown'}"
            if node:
                previous = re.sub(r"^# @[^\s]+\s*", "", self.trailing(node))
                if previous:
                    comment += " " + (
                        previous if previous.startswith("#") else "# " + previous
                    )
                indentation = self.lines[node.lineno - 1][: node.col_offset]
                edits.append(
                    (
                        node.lineno - 1,
                        node.end_lineno,
                        f"{indentation}{self.register.args.args[0].arg}.pin({arguments}) {comment}\n",
                    )
                )
            else:
                additions.append(
                    f"{self.indentation}{self.register.args.args[0].arg}.pin({arguments}) {comment}\n"
                )
        for name in remove:
            if node := self.declarations.get(name):
                edits.append((node.lineno - 1, node.end_lineno, ""))
        if additions:
            position = self.register.body[-1].end_lineno
            prefix = "" if self.lines[position - 1].endswith("\n") else "\n"
            edits.append((position, position, prefix + "".join(additions)))
        lines = list(self.lines)
        for start, end, replacement in sorted(edits, reverse=True):
            lines[start:end] = [replacement]
        rendered = "".join(lines)
        # Removing the last statement must leave a valid function body.
        try:
            ast.parse(rendered)
        except IndentationError:
            position = self.register.lineno
            lines = rendered.splitlines(keepends=True)
            lines.insert(position, f"{self.indentation}pass\n")
            rendered = "".join(lines)
            ast.parse(rendered)
        return rendered
