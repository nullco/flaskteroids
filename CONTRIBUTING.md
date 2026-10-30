# Contributing to Flaskteroids

Contributions to code, tests, and guides are welcome. If you are unsure where to
start, open an [issue](https://github.com/nullco/flaskteroids/issues) to discuss
an idea.

## Report a bug or suggest a feature

For a bug, include the Flaskteroids and Python versions, steps to reproduce the
problem, and what you expected to happen. A small example or failing test helps
make the report actionable.

For a feature, describe the application workflow you want to support. Explain
the problem before proposing an implementation.

## Set up the project

You will need Python 3.14 or newer, Git, and
[uv](https://docs.astral.sh/uv/getting-started/installation/).

Fork the repository, clone your fork, and run these commands from its root:

```sh
uv sync --locked --dev
uv run playwright install chromium
```

This installs the locked development dependencies and the browser used by
system tests.

## Make and check a change

Keep changes focused and add tests for the behavior you are changing. Run a
specific test file while working:

```sh
uv run pytest tests/path/to/test_file.py
```

Before opening a pull request, run the quality checks and complete test suite:

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -n auto --dist loadfile -q
```

See [AGENTS.md](AGENTS.md) for project conventions, testing expectations, and
the scope of linting and type checks.

## Improve the guides

Follow [Writing guides](docs/contributing/guides.md). Teach a focused workflow,
explain what examples accomplish, and keep API reference material separate.

Update links and `mkdocs.yml` when moving or adding a page. Build the site using
the documentation tooling:

```sh
uv tool run --with mkdocs-material mkdocs build --strict
```

## Open a pull request

Explain the problem, summarize the change, and describe how you checked it.
Include any documentation updates needed to use the changed behavior.

Release instructions are in [RELEASING.md](RELEASING.md). Logos and usage
guidance are in [branding/](branding/README.md).
