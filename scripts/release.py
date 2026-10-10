"""Release bookkeeping used by the GitHub Actions release workflows."""

import argparse
from datetime import date
from pathlib import Path
import re
import tomllib


VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+")


def current_version(root):
    project = tomllib.loads((root / "pyproject.toml").read_text())
    version = project["project"]["version"]
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError("Releases require a stable version in X.Y.Z format")
    return version


def changelog_section(content, heading):
    matches = list(re.finditer(rf"(?m)^{heading}\s*$", content))
    if len(matches) != 1:
        raise ValueError("Expected exactly one matching changelog heading")
    start = matches[0].end()
    next_heading = re.search(r"(?m)^## ", content[start:])
    end = start + next_heading.start() if next_heading else len(content)
    notes = content[start:end].strip()
    if not re.sub(r"<!--.*?-->", "", notes, flags=re.S).strip():
        raise ValueError("Add user-facing release notes to CHANGELOG.md first")
    return matches[0].start(), end, notes


def release_notes(root):
    version = current_version(root)
    content = (root / "CHANGELOG.md").read_text()
    _, _, notes = changelog_section(
        content, rf"## {re.escape(version)} - \d{{4}}-\d{{2}}-\d{{2}}"
    )
    return notes


def prepare_release(root, bump):
    version = current_version(root)
    parts = [int(part) for part in version.split(".")]
    index = {"major": 0, "minor": 1, "patch": 2}[bump]
    parts[index] += 1
    parts[index + 1 :] = [0] * (2 - index)
    new_version = ".".join(str(part) for part in parts)

    changelog_path = root / "CHANGELOG.md"
    changelog = changelog_path.read_text()
    start, end, notes = changelog_section(changelog, "## Unreleased")
    if re.search(rf"(?m)^## {re.escape(new_version)}(?:\s|$)", changelog):
        raise ValueError(f"Changelog already contains version {new_version}")
    section = (
        f"## Unreleased\n\n## {new_version} - {date.today().isoformat()}\n\n{notes}\n\n"
    )
    new_changelog = changelog[:start] + section + changelog[end:]

    project_path = root / "pyproject.toml"
    project = project_path.read_text()
    project_section = re.search(r"(?ms)^\[project\][^\S\n]*\n(.*?)(?=^\[|\Z)", project)
    if project_section is None:
        raise ValueError("Expected a [project] section in pyproject.toml")
    new_section, count = re.subn(
        rf"(?m)^(version\s*=\s*)([\"']){re.escape(version)}\2",
        lambda match: f"{match[1]}{match[2]}{new_version}{match[2]}",
        project_section[1],
    )
    if count != 1:
        raise ValueError("Expected exactly one project version assignment")
    new_project = (
        project[: project_section.start(1)]
        + new_section
        + project[project_section.end(1) :]
    )
    project_path.write_text(new_project)
    changelog_path.write_text(new_changelog)
    return new_version


def validate_tag(root, tag):
    version = current_version(root)
    if tag != f"v{version}":
        raise ValueError(f"Release tag must be v{version}, got {tag!r}")
    lock = tomllib.loads((root / "uv.lock").read_text())
    packages = [p for p in lock["package"] if p["name"] == "flaskteroids"]
    if len(packages) != 1 or packages[0]["version"] != version:
        raise ValueError("uv.lock does not match the project version; run uv lock")
    release_notes(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("bump", choices=("patch", "minor", "major"))
    commands.add_parser("version")
    commands.add_parser("notes")
    validate = commands.add_parser("validate-tag")
    validate.add_argument("tag")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            print(prepare_release(args.root, args.bump))
        elif args.command == "version":
            print(current_version(args.root))
        elif args.command == "notes":
            print(release_notes(args.root))
        else:
            validate_tag(args.root, args.tag)
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
