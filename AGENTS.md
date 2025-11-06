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
*   **Dependency Management:** `uv` (used for `uv pip install -r requirements.txt` or `uv sync`).
*   **Virtual Environment:** `.venv/`

## Common Commands

### Running Tests

*   **Unit/Integration Tests:** `pytest`
*   **Specific Test File:** `pytest tests/path/to/your_test_file.py`
*   **Coverage Report:** `pytest --cov=flaskteroids --cov-report=html`

### Linting and Formatting

*   **Linting (Ruff):** `ruff check .`
*   **Formatting (Ruff):** `ruff format .`


### Tests implementation

When implementing tests, consider the following

* Use pytest and pytest-mock conventions
* Use pytest fixtures
* Keep code simple and out of unnecessary comments
* Only test things via their public APIs. (No _ methods, etc)


