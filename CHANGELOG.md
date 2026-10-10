# Changelog

## Unreleased

### Added

- Model validations and Rails-style lifecycle callbacks, including transaction
  commit and rollback callbacks.
- Application configuration with environment-specific settings, `database.yml`,
  encrypted credentials, and boot-time initializers.
- A pytest-based application testing framework with transactional tests, YAML
  fixtures, integration tests, job and mail assertions, and Playwright system
  tests. Run tests with `flask test` and `flask test:system`.
- Generated application metadata in `pyproject.toml`, Docker and Kamal deployment
  scaffolding, and `bin/setup` and `bin/release` helpers.
- Maintainer-driven release automation: choose a version bump, review a release
  PR, and publish a draft GitHub release to trigger validated PyPI publishing.

### Breaking changes

- Applications now boot through `Application.initialize()` instead of
  `create_app()`. Existing applications must migrate their boot and configuration
  files to the new layout. See the
  [configuration guide](https://nullco.github.io/flaskteroids/configuration/).
- Generated production applications require an encryption key for credentials;
  provide `FLASKTEROIDS_MASTER_KEY` when deploying.
- Python 3.12 or newer is required.

### Fixed

- Inflection handling for empty strings and additional irregular words.
