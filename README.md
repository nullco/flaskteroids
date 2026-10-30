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

## What is Flaskteroids?

Flaskteroids—**Flask on steroids**—is a Python framework for building
database-backed web applications. It brings Flask, SQLAlchemy, and Celery into a
shared workflow, with conventions for where code belongs and tools for the tasks
applications need every day.

Instead of assembling a stack and connecting its pieces yourself, you start with
models, routing, templates, forms, background jobs, email, and testing that work
together. Generators create ordinary application code that you can read and change.

Applications follow the **Model-View-Controller (MVC)** pattern. Each layer has a
clear responsibility.

### Models

Models represent your application's data and business rules: a product, an
account, or a subscription. Migrations describe the database structure; model
classes define validations, associations, and behavior.

You can create, query, and save records without managing database sessions.
See [Model basics](https://nullco.github.io/flaskteroids/models/).

### Views

Views are Jinja templates that turn application data into HTML. Layouts and
partials share markup, helpers share presentation logic, and model-backed forms
display values and validation errors.

Use Turbo Frames and Streams when a page needs inline navigation or partial
updates. See [Templates and helpers](https://nullco.github.io/flaskteroids/views/).

### Controllers

Controllers handle requests, work with models, and choose a response. Routes
connect URLs to controller actions; actions can render a page, return JSON, or
redirect the browser.

You can also generate an API-only application for a mobile client or a separate
frontend. See [Controller basics](https://nullco.github.io/flaskteroids/controllers/)
and [Building an API](https://nullco.github.io/flaskteroids/controllers/api/).

## Beyond requests and pages

The same application structure supports:

- [Background jobs](https://nullco.github.io/flaskteroids/other/jobs/) for work
  outside a request.
- [Mailers](https://nullco.github.io/flaskteroids/other/mailers/) for composing,
  previewing, and delivering email.
- [Attachments](https://nullco.github.io/flaskteroids/other/attachments/) for file
  uploads, local storage, and optional storage providers.
- [Rich text](https://nullco.github.io/flaskteroids/other/rich_text/) with the
  Lexxy editor and safe HTML rendering.
- [Internationalization](https://nullco.github.io/flaskteroids/other/internationalization/)
  for translated messages and localized dates and times.
- [Configuration](https://nullco.github.io/flaskteroids/configuration/) for
  environments, database connections, and encrypted credentials.
- [Testing](https://nullco.github.io/flaskteroids/testing/) with pytest-based
  tests, fixtures, job and mail assertions, and Playwright browser tests.

## Getting started

You will need Python 3.14 or newer, Git, Bash, and
[uv](https://docs.astral.sh/uv/getting-started/installation/).
The commands below assume Linux, macOS, or Windows through WSL. SQLite is
included with Python, so you do not need a separate database server to get started.

### Create an application

Install Flaskteroids in a Python virtual environment:

```sh
python3 -m venv flaskteroids-env
source flaskteroids-env/bin/activate
pip install flaskteroids
```

Create your application and start its server:

```sh
flask new my_app
cd my_app
bin/flask run
```

Open <http://127.0.0.1:5000> to see the welcome page.

The generator installs the application's dependencies into its own `.venv` and
prepares the development database. From now on, run commands from the application
root with `bin/flask`; it uses that environment automatically.

### Add your first resource

Stop the server and generate a posts interface:

```sh
bin/flask generate scaffold Post title:string content:text
bin/flask db:migrate
bin/flask run
```

Visit <http://127.0.0.1:5000/posts> to create, view, edit, and delete posts.
The scaffold creates a model, migration, controller, templates, routes, and tests.
These are your application's files, ready to customize.

In another terminal, run the generated tests from `my_app`:

```sh
bin/flask test
```

### Keep learning

Follow the [store tutorial](https://nullco.github.io/flaskteroids/getting_started/)
to build a product catalog step by step, then add login, images, restock emails,
and tests. Use the [component guides](https://nullco.github.io/flaskteroids/#find-a-guide)
when you want to explore one feature.

On a fresh checkout of an application, run `bin/setup` to install dependencies
and prepare the database. Commit `uv.lock` to share dependency versions, but
never commit `config/master.key`. Your generated `deploy/README.md` explains
Docker and deployment.

## Coding agents

Generated applications include `.agents/skills/using-flaskteroids/SKILL.md`,
which points coding agents to guidance for the installed framework version.
You can also locate that guidance from the application's Python environment:

```sh
bin/flask agent-skills path
```

Read `using-flaskteroids/SKILL.md` in the printed directory. The guidance directs
agents to use public framework APIs for supported tasks.

## Contributing

Contributions to code, tests, and guides are welcome.
See [Contributing to Flaskteroids](CONTRIBUTING.md) to get started.

## License

Flaskteroids is released under the [MIT License](LICENSE).
