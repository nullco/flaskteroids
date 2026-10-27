<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/nullco/flaskteroids/main/branding/logo-horizontal-dark.svg">
    <img src="https://raw.githubusercontent.com/nullco/flaskteroids/main/branding/logo-horizontal-light.svg" alt="Flaskteroids" width="560">
  </picture>
</h1>

<p align="center">
  A batteries-included Python MVC framework built on Flask, SQLAlchemy, and Celery.
</p>

<p align="center">
  <a href="https://github.com/nullco/flaskteroids/actions/workflows/test.yml?query=branch%3Amain++" target="_blank">
    <img src="https://github.com/nullco/flaskteroids/actions/workflows/test.yml/badge.svg?event=push&branch=main" alt="Build Status">
  </a>
  <a href="https://pypi.org/project/flaskteroids/" target="_blank">
    <img src="https://img.shields.io/pypi/v/flaskteroids.svg?color=28a745" alt="PyPI Version">
  </a>
  <a href="https://pypi.org/project/flaskteroids/" target="_blank">
    <img src="https://img.shields.io/pypi/pyversions/flaskteroids.svg" alt="Python Versions">
  </a>
  <a href="https://github.com/nullco/flaskteroids/blob/main/LICENSE" target="_blank">
    <img src="https://img.shields.io/github/license/nullco/flaskteroids.svg" alt="License">
  </a>
</p>

---

Build web applications with a consistent layout and tools that work together.
Flaskteroids provides models, controllers, templates, forms, jobs, and email, with
generators to create the starting code.

Flask handles HTTP requests, SQLAlchemy and Alembic handle the database, and
Celery runs background jobs. You can use their native APIs when you need more
control, without giving up the framework's everyday workflows.

## What's included

- Resource routing with CRUD routes and path helpers.
- [API-only applications](https://nullco.github.io/flaskteroids/controllers/api/) with JSON scaffolds and request tests.
- Models with associations, validations, and lifecycle callbacks.
- Jinja templates, form helpers, and HTML or JSON responses.
- [Turbo Frames and HTTP Streams](https://nullco.github.io/flaskteroids/views/turbo/) with a locally bundled Turbo runtime.
- YAML translations, scoped locales, pluralization, and localized date/time formats.
- Generators for models, migrations, controllers, scaffolds, mailers, and authentication.
- Background jobs and email delivery.
- File attachments with disk and S3-compatible storage.
- Rich-text fields with an integrated Trix editor and safe HTML rendering.
- Environment settings, `database.yml`, encrypted credentials, and boot-time initializers.
- Pytest-based transactional tests, YAML fixtures, job and mail assertions, and Playwright browser tests.

## Installation

Requires Python 3.14 or newer. Install Flaskteroids in your Python environment:

```sh
pip install flaskteroids
```

## Getting started

Create an application. Git, Bash, and [uv](https://docs.astral.sh/uv/getting-started/installation/) must be installed.

```sh
flaskteroids new my_app
cd my_app
```

Generation installs dependencies and prepares your development database.
Run application commands with `bin/flask`; no environment activation is needed.
Start the server:

```sh
bin/flask run
```

Open <http://127.0.0.1:5000> to see the welcome page.

```sh
bin/flask test
bin/flask test:system
```

The app includes a health test. An empty system suite succeeds without a browser.

## Add a posts resource

Stop the server and run these commands inside `my_app`:

```sh
bin/flask generate scaffold Post title:string content:text
bin/flask db:prepare
bin/flask run
```

The scaffold generates a model, migration, controller, views, and routes. Visit
`http://127.0.0.1:5000/posts` to create, view, edit, and delete posts.

## Next steps

For a step-by-step tutorial, follow [Getting started with Flaskteroids](https://nullco.github.io/flaskteroids/getting_started/).
Build a product catalog while learning models, controllers, forms, authentication,
uploads, email, and testing.

- Run `bin/setup` for a fresh checkout or after changing dependencies. Commit `uv.lock`.
- To defer installation, use `flaskteroids new my_app --skip-install`, then run `bin/setup` later.
- See [Testing](https://nullco.github.io/flaskteroids/testing/) for browser setup and [Configuration](https://nullco.github.io/flaskteroids/configuration/) for environments and secrets.
- Your generated `deploy/README.md` explains Docker and deployment.

Use the [guide index](https://nullco.github.io/flaskteroids/#find-a-guide) to find
help with models, routes, forms, encryption, background jobs, and other tasks.

## Agent skills

Flaskteroids bundles coding guidance for agents with each release. New applications
include `.agents/skills/using-flaskteroids/SKILL.md`, which points agents to
instructions for the installed framework version. These instructions require
agents to use public Flaskteroids APIs when they cover the task, rather than
calling dependency internals.

In your application's Python environment, locate the installed skills with:

```sh
flaskteroids agent-skills path
```

The command prints the absolute skills directory path. Read
`using-flaskteroids/SKILL.md` inside that directory for version-matched guidance.
No application configuration or initialization is required.

## Development

Use the committed lock and the same check-only commands as CI:

```sh
uv sync --locked --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run playwright install chromium
uv run pytest -q
```

Ruff uses the Python 3.14 / 88-column policy in `pyproject.toml`. Mypy checks
only declaration records, queue adapters, and a static contract probe, not the
whole ORM or generated applications. Raw Mako templates are excluded; generated
samples are validated separately and are not promised Ruff-clean.
See [AGENTS.md](AGENTS.md) for scope and contributor-only fixing commands.
Repository logos and usage guidance are in [branding/](branding/README.md).

## Releasing

See [the release guide](RELEASING.md) for release PRs and PyPI publishing.

## License

Flaskteroids is released under the [MIT License](LICENSE).
