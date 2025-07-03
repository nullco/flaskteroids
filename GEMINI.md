# Project: Flaskteroids

This document contains project-specific information to assist the Gemini CLI agent.

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

## Project Conventions
