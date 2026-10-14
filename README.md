<h1 align="center">Flaskteroids</h1>

<p align="center">
  A Rails-inspired Python MVC framework built on Flask, SQLAlchemy, and Celery.
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

Flask handles HTTP requests, SQLAlchemy and Alembic handle the database, and Celery runs background jobs.

Models, controllers, and templates live in conventional directories. The framework discovers them without manual registration. Flask APIs and extensions remain available when you need them.

## What's included

- Resource routing with CRUD routes and path helpers.
- Models with associations, validations, and lifecycle callbacks.
- Jinja templates, form helpers, and HTML or JSON responses.
- Generators for models, migrations, controllers, scaffolds, mailers, and authentication.
- Background jobs and email delivery.
- File attachments with disk and S3-compatible storage.
- Environment settings, `database.yml`, encrypted credentials, and boot-time initializers.
- Pytest-based transactional tests, YAML fixtures, job and mail assertions, and Playwright browser tests.

## Installation

Requires Python 3.12 or newer. Install Flaskteroids in your Python environment:

```sh
pip install flaskteroids
```

## Getting started

Create an application. Git, Bash/POSIX, and uv must be installed.

```sh
flaskteroids new my_app
cd my_app
```

Generation installs dependencies, creates the app lock, prepares SQLite and
initializes Git. Use `bin/setup` for fresh checkouts or changed dependencies;
`--skip-install` defers installation/preparation. Commit `uv.lock`.
Start the server without activating an environment:

```sh
bin/flask run
bin/flask test
bin/flask test:system
```

Open `http://127.0.0.1:5000` to see the welcome page.

## Add a posts resource

Stop the server and run these commands inside `my_app`:

```sh
bin/flask generate scaffold Post title:string content:text
bin/flask db:prepare
bin/flask run
```

The scaffold generates a model, migration, controller, views, and routes. Visit
`http://127.0.0.1:5000/posts/` to create, view, edit, and delete posts.

See the [documentation](https://nullco.github.io/flaskteroids/) for configuration,
testing, and the API guides.

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

## Releasing

See [the release guide](RELEASING.md) for release PRs and PyPI publishing.

## License

Flaskteroids is released under the [MIT License](LICENSE).
