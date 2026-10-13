# Changelog

## Unreleased

### Changed

- Only `None` triggers implicit controller template rendering. Explicit empty
  responses are returned unchanged.
- Around-action generators may halt before yielding by returning a response.
  Generators that run the action must yield exactly once.
- Model JSON now includes only database columns and pending column changes,
  excluding password attributes, digests, confirmations, and reset tokens,
  including custom secure-password field names. Virtual fields and associations
  require an explicit `__json__()` override. Model-backed forms no longer use
  response serialization to populate their fields.
- HTML helpers escape ordinary text and attributes. Trusted `Markup` is supported
  for link/button text and select labels, while field values remain escaped.
  Unsupported URL schemes, control characters in URLs, and invalid HTML attribute
  names now raise `ValueError`.

### Fixed

- Preserve JSON response status codes and support ordinary JSON payloads,
  including empty values and `null`. Model errors serialize as full-message
  lists, so scaffold JSON validation failures return 422 rather than 500.
- Unwind entered around-action generators on action and setup failures. Continue
  cleanup after a cleanup error without replacing the original exception; log
  secondary failures and attach them as exception notes. After callbacks run
  only after the action and around cleanup succeed.
- Stop JSON serialization and form rendering from generating password reset tokens.
- Escape select options and prompts, labels, textarea field names, and submit
  values. Compare unescaped select values so values containing HTML characters
  remain selectable without double escaping.

## 0.4.0 - 2026-10-12

### Added

- Chainable `limit()` and `offset()` queries for SQL pagination, plus `order()`
  directly on models. `count()`, `first()`, and `last()` respect the selected page.
- New applications include `.agents/skills/using-flaskteroids/SKILL.md`, a loader
  for the installed framework's version-matched agent guidance. The bundled
  guidance requires agents to use framework APIs before writing custom code.
- Support for Python 3.14 and 3.15, with CI coverage.
- File attachments with disk and optional S3-compatible storage, signed download
  links, upload validation, and background deletion.
- `flask attachments:install`, `config/storage.yml`, attachment generator
  fields, multipart form helpers, fixture uploads, and isolated test storage.

### Changed

- Testing tools are core dependencies. Applications no longer need a separate
  development dependency group to run `flask test` or `flask test:system`.
- Updated minimum dependency versions and package license metadata.
- Restored the standard dynamic PyPI version badge, displayed in green. Release
  preparation no longer modifies the README.
- Declare Python 3.12 through 3.15 in package classifiers, matching the CI matrix.
- Revised the README and guides with shorter explanations and corrected examples.

### Fixed

- Bind CSRF tokens to browser sessions and reject tokens from other sessions.
- Expire password reset tokens after 15 minutes and invalidate them after a
  successful password change. Tokens are scoped to the model and password field.
- Generate authentication migrations for the conventional `users` and `sessions`
  tables instead of `users_tables` and `sessions_tables`.
- Render escaped textarea values between the tags instead of in a `value`
  attribute.

### Upgrade notes

- Reload open forms after upgrading. Previously issued CSRF tokens are rejected.
  Token generation requires an active request context and a configured secret key.
  Do not put pages containing session-specific CSRF tokens in a shared cache.
- Users with existing password reset links must request new ones. Handle
  `itsdangerous.SignatureExpired` and `itsdangerous.BadSignature` when verifying
  expired, invalid, or revoked reset tokens.
- The authentication generator fix applies to newly generated migrations. Inspect
  existing authentication table names and migrate them to `users` and `sessions`
  if the older generator created `users_tables` and `sessions_tables`.

### Fixed

- Use modern SQLite transaction control so releasing a savepoint does not commit
  attachment changes before the outer transaction commits. Enable SQLite foreign
  keys to protect referenced blobs and other database relationships.
- Keep model commit and rollback callbacks scoped to their transactions and
  savepoints.
- Generated login controllers now pass scalar fields correctly to `params.expect`.
- Scaffold creation saves once rather than calling both `create` and `save`.

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

- Model validations and lifecycle callbacks, including transaction
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

