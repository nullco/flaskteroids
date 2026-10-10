# Changelog

## Unreleased

### Added

- Support for Python 3.14 and 3.15, with CI coverage.

### Changed

- Reverted release-specific PyPI badge URLs and restored the standard dynamic
  badge. Release preparation no longer modifies the README.
- Display the PyPI version badge in green.
- Declare Python 3.12 through 3.15 in package classifiers, matching the CI matrix,
  so the Python badge lists specific supported versions.

## 0.3.1 - 2026-10-10

### Fixed

- Refresh the README's PyPI version badge URL with each release to reduce stale
  cached version badges on GitHub and PyPI.

## 0.3.0 - 2026-10-10

### Added

- A version-matched `using-flaskteroids` agent skill bundled with the framework,
  encouraging agents to use existing commands and their installed help.
- `flaskteroids agent-skills path` to locate the installed skills directory
  without initializing an application.

### Changed

- CLI help now includes concise command summaries, usage examples, prerequisites,
  and important safety notes.
- Model, migration, resource, and scaffold generators now show `NAME [FIELDS]...`
  usage and report missing names as clear usage errors.

## 0.2.0 - 2026-10-10

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

