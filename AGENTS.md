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

## Import discipline

* Keep imports at module scope in framework code, tests, and generated code.
* Do not put imports inside functions or methods to hide circular dependencies,
  defer ordinary dependencies, or make an import error disappear. Fix the module
  boundaries instead: extract shared types or services into lower-level modules
  and keep dependencies flowing in one direction.
* Function-local imports are allowed only for genuinely optional dependencies
  (such as the S3 extra) or tests specifically exercising import timing/order.
  Keep these exceptions narrow and explain why they are necessary. A lint
  exemption is not permission to use local imports elsewhere.
* Module-level `TYPE_CHECKING` imports are appropriate for type-only dependencies;
  do not replace runtime dependencies with typing tricks.

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

When implementing or cleaning up tests:

* Use pytest and pytest-mock conventions and fixtures.
* Avoid duplication: share setup with fixtures and parameterize cases that verify
  the same behavior. Keep distinct contracts and testing layers explicit.
* Write affirmative, behavior-focused names (`test_save_persists_valid_record`),
  rather than vague labels or statements about what does not happen. Error and
  security contracts belong here too (`test_save_rejects_invalid_record`); retain
  meaningful rejection, failure, and boundary coverage.
* Test the current supported public API, not backward compatibility with retired
  APIs, import paths, or data formats.
* Remove obsolete scenarios and assertions when their behavior is no longer part
  of the supported contract. Keep regression tests for behavior that remains
  relevant, naming them after that behavior rather than its history.
* Keep executable test suites, subprocess scenarios, and substantial application
  fixtures in normal source files, copied or executed by the test as needed. Do not
  embed whole programs in strings; pass varying inputs as arguments or environment
  values. Small snippets are appropriate when source text itself is the test input
  (for example, parser cases, malformed modules, or import-failure probes).
* Assert the behavior named by the test, not every observable detail. Prefer
  parsed HTML/JSON, public state, exception types, and structured reports over
  exact prose, whitespace, attribute order, or fixed test-count summaries. Keep
  exact values when they define the contract (for example, status codes, escaping,
  custom messages, or deliberately tested output formats), and keep failures
  diagnostic. Avoid repeating low-level assertions in higher-level workflows.
* Keep code simple and avoid unnecessary comments.
* Only test through public APIs (no private methods, etc.).

## Rails-first developer experience

The primary design priority is a consistent Rails-like developer experience in
Python. Flaskteroids is a Rails-like framework implemented using Flask,
SQLAlchemy, and Celery, not merely a thin facade over their native APIs.

* Favor Rails-like application workflows and observable behavior, not just
  Rails-inspired method names. Keep Python syntax idiomatic where appropriate.
* Implementation may differ substantially from Rails. Internal simplicity,
  native backend interoperability, or fewer framework abstractions must not
  take precedence over a coherent application-facing experience.
* Ordinary framework tasks should not require understanding SQLAlchemy mapping,
  session enrollment, flushing, or attribute history. Native APIs are optional
  advanced escape hatches with explicit boundaries, not prerequisites for the
  normal developer workflow.
* Preserve consistent contracts across assignment, validation failures, form
  redisplay, queries, association operations, callbacks, transactions, migrations,
  and generators. Do not leak backend behavior into these contracts by accident.
* Accept bounded implementation complexity and adapters when they materially
  improve developer experience. Delegate machinery to dependencies where useful;
  avoid unnecessarily duplicating identity maps, relationship caches, or
  persistence engines. An application-facing association proxy is not inherently
  undesirable merely because it is a framework abstraction.
* Evaluate alternatives against public behavior contracts and representative
  generated-application workflows, not only implementation size or native
  SQLAlchemy compatibility. Check relevant Rails behavior before claiming parity.
* When a Rails-like contract conflicts with backend behavior or an existing
  architecture decision, surface the trade-off before changing the public API.
  Do not silently weaken the developer experience to accommodate implementation
  convenience. Record intentional deviations and their rationale, with tests.

These priorities guide design decisions; they do not require literal Ruby syntax,
complete Rails feature parity, or unrelated architectural rewrites.


