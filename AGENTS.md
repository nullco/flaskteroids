# Project: Flaskteroids

This document contains project-specific information to assist the Gemini CLI agent.

## Project Philosophy

This is a batteries included MVC framework built on top of Flask, Celery, and SQLAlchemy.

The idea of this framework is to bring the proven philosophy and design principles of Ruby on Rails to the Python ecosystem. It aims to make web development fast, coherent, and enjoyable by embracing a strong set of conventions, prioritizing developer productivity, and providing a complete, integrated toolset.

Key goals include:

    * Eliminate unnecessary configuration through convention over configuration.

    * Encourage maintainable code by applying the Don't Repeat Yourself (DRY) principle.

    * Promote clean architecture using the Model-View-Controller (MVC) pattern.

    * Offer an integrated stack for routing, ORM, templating, testing, and more—designed to work seamlessly together.

    * Support RESTful application design with sensible defaults for resourceful routing.

    * Provide first-class support for testing at all levels of the application.

    * Leverage Python’s capabilities to offer concise, expressive APIs and domain-specific abstractions.

    * Focus on developer happiness, making common tasks simple, elegant, and consistent.

This framework provides a collection of tools and a cohesive ecosystem with a clear vision: to enable developers to build high-quality web applications with confidence and speed, without sacrificing code clarity or long-term maintainability.


## General Information

*   **Project Type:** Python web framework.
*   **Primary Language:** Python 3.12+
*   **Dependency Management:** `uv`; reproduce the development environment with `uv sync --locked --dev`.
*   **Virtual Environment:** `.venv/`

## Common Commands

### Running Tests

*   **Unit/Integration Tests:** `pytest`
*   **Specific Test File:** `pytest tests/path/to/your_test_file.py`
*   **Coverage Report:** `pytest --cov=flaskteroids --cov-report=html`

### Linting and Formatting

*   **Linting (check only):** `ruff check .` or `uv run ruff check .`
*   **Formatting (check only):** `ruff format --check .` or `uv run ruff format --check .`
*   **Contributor fixes (review the diff):** `uv run ruff check --diff .`, then `uv run ruff check --fix .`; format separately with `ruff format .` or `uv run ruff format .`. Do not apply unsafe fixes wholesale.

Use `uv run pytest` for tests in the locked environment. Ruff policy lives only in
`pyproject.toml`: Python 3.12, 88 columns, stable double-quoted/space formatting.
Discovery includes `*.py`, `*.pyi`, and `pyproject.toml`, retaining standard cache/
VCS exclusions and excluding build, dist, htmlcov, egg-info and raw `*.mako`
resources even for explicit file arguments. Copied Alembic `env.py` stays in scope;
Markdown, notebooks and raw templates do not. Rendered applications are checked
separately, with `--config /absolute/path/to/framework/pyproject.toml`; generated
output is not universally lint/format-clean.


### Scoped typing

Run `uv run mypy` (also enforced by CI). Explicit default targets are
`flaskteroids/declarations.py`, `flaskteroids/jobs/adapters.py`, and the static-only
`tests/typing/queue_adapter_contract.py` probe. Imported project types are analyzed
silently, not globally skipped; only missing Celery stubs are exempted. Job
arguments/configuration remain dynamic and enqueue results may be any `object`.
This is not repository-wide ORM or generated-application typing.

CI's `Quality` job runs these three check-only commands on Python 3.12 without a
browser. Keep the browser-enabled Python 3.12–3.15 test matrix intact. Repository
administrators should require `Quality` alongside existing test checks in branch
protection; reusable release callers already wait for the entire test workflow.

### Tests implementation

When implementing tests, consider the following

* Use pytest and pytest-mock conventions
* Use pytest fixtures
* Keep code simple and out of unnecessary comments
* Only test things via their public APIs. (No _ methods, etc)


