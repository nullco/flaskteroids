# Changelog

## Unreleased

### Breaking changes

- Replace the standalone `flaskteroids` CLI with Flask CLI plugins. Use `flask new`
  and `flask agent-skills path`; asset and import-map commands also run through
  `flask` without application boot. The `flaskteroids` executable and
  `python -m flaskteroids` entry point are removed.

### Added

- Rails-style import maps with explicit Python pin configuration, local directory
  pins, Jinja module helpers, preloading, optional integrity, and bootless package
  pin/unpin/update/pristine commands using JSPM. Generated browser applications
  include the entrypoint and bin/importmap. See [Import maps](docs/other/importmaps.md).

### Changed

- Rich text now uses packaged Lexxy modules and stylesheets through import maps,
  replacing Trix directly. Forms use native form-associated editor controls;
  editor HTML is exposed through to_editor_html(). Uploads retain the existing
  authorization and storage services, with cancellation, progress, validation
  redisplay, alternative text, safe image links, and gallery rendering.
  Sanitization preserves headings, tables, code languages, and safe highlights.
  rich_text:install configures modules without copying assets; --force is removed.
- Lexxy now ships through flaskteroids-lexxy, independently of Flaskteroids.
  Generated browser applications include it by default.
- Turbo now ships through flaskteroids-turbo and import maps without copying assets.
  Generated browser applications include it by default. Application turbo.js assets
  can override the packaged runtime.
- turbo:install configures import maps and preserves application code; its asset
  replacement --force option is removed. New importmap:install provides the same
  setup directly.
- Asset discovery includes app/javascript and vendor/javascript, with application
  overrides for explicitly exposed framework assets. Duplicate logical names
  across application sources and overlapping source directories fail explicitly.

## 0.11.0 - 2026-10-28

### Breaking changes

- Rename the browser controller base from `ActionController` to `Controller`.
  Update imports and base classes; `APIController` is unchanged and the old
  name is removed.
- Rename the mailer base from `ActionMailer` to `Mailer`. Update imports and base
  classes; the old name is removed.
- Rename `config.action_controller` to `config.controller` and
  `config.action_mailer` to `config.mailer`; the old namespaces are removed.
- Rename `flaskteroids.actions.ActionParameters` to `flaskteroids.actions.Parameters`;
  the old class name is removed.
- Rename `Mailer.with_(...)` to `Mailer.with_params(...)` for explicit
  mailer parameter assignment. Update mailer calls in existing applications;
  the `with_` name is removed.
- Browser test helpers `fill_in(...)` and `fill_in_rich_text_area(...)` now take
  `value=` instead of `with_=`. Update system tests; the old keyword is removed.
- Rename the rate limiter's custom-handler keyword from `with_=` to `using=`.
  Update controller declarations; the old keyword is removed.
- Individual route names use `aka=` instead of `as_=`.
- Mailer From addresses use `by=` instead of `from_=`, including the
  `config.mailer.default_options["by"]` setting.
- Model callback conditions use `when=` and `unless=` instead of `if_=` and
  `unless_=`.
- `assert_changes(..., was=..., to=...)` replaces the `from_=` keyword;
  `to=` is unchanged. The old keyword aliases are removed.

## 0.10.0 - 2026-10-27

### Breaking changes

- Drop Python 3.12 and 3.13 support. Flaskteroids and newly generated applications
  now require Python 3.14 or newer; generated Docker images use Python 3.14.
  Upgrade development and deployment runtimes before updating Flaskteroids.

### Added

- API-only application generation with `new --api`, `APIController`, JSON request
  parameters and conventional root wrapping, JSON CRUD scaffolds and request
  tests, and API-aware routing, boot, CI, and Docker defaults. Authentication
  generation and cookie-session opt-ins remain deferred.
- Explicit `JSONValue` strong-parameter schemas for JSON columns; scaffolds retain
  complete JSON values without broadening other fields' allowlists.

## 0.9.0 - 2026-10-26

### Breaking changes

- Links, buttons, forms, and Turbo tags now normalize `class_` to `class` rather
  than emitting a literal `class_` attribute; nested `data`/`aria` dictionaries and
  boolean attributes use HTML-aware serialization with escaped values.
- New generated pages use `{% extends layout %}`, scaffold record IDs use
  underscored `dom_id` values, and scaffold update redirects use 303. New app
  layouts load a local Turbo runtime and include the CSRF meta token. These are
  intentional generator-output changes, not removals of existing public APIs;
  existing literal layout inheritance still works and views are not rewritten.
- Job configuration now lives under `config.jobs`. Update application and
  environment settings to use this namespace; queue adapter behavior is unchanged.
- Rename `ActionMailer.with_params(...)` to `ActionMailer.with_(...)`; the old
  name is removed.
- Attribute encryption uses `config.encryption`, the `encryption` credentials
  section, and `FLASKTEROIDS_ENCRYPTION_*` environment variables. Update existing
  encryption settings to these names; key material and ciphertext are unchanged.
- Framework environment overrides use `FLASKTEROIDS_ENV`,
  `FLASKTEROIDS_DATABASE_URL`, `FLASKTEROIDS_SECRET_KEY_BASE`, and
  `FLASKTEROIDS_ATTACHMENTS_SERVICE`. Update deployment variables and generated
  setup/test/Docker configuration. Python settings and credential names remain
  unprefixed; dependency-owned variables retain their native names.

### Added

- Rails-style Turbo Frames and HTTP Stream responses: record DOM IDs, frame tags,
  partial rendering, Stream builders/templates, HTML/JSON/Stream negotiation,
  resource `.turbo_stream` URLs, frame-aware layouts, and representation-aware
  cache boundaries. No live subscriptions or broadcasts are included.
- Bundled upstream Turbo 8.0.23 with license/provenance and `turbo:install` for
  existing applications. Installation preserves app-owned assets unless `--force`
  is supplied and migrates the known generated CDN URL; custom layouts receive
  instructions. See [Turbo Frames and Streams](docs/views/turbo.md).
- Dependency-free internationalization with YAML catalogs, scoped locales,
  Python/controller/Jinja translation and localization helpers, interpolation,
  configurable plural rules, safe HTML translations, and locale-aware mail delivery.
  New applications include an English catalog and a locale-aware layout language.
- Rich-text attributes with `has_rich_text`, a locally bundled Trix editor,
  server-sanitized rendering, eager-loading scopes, and scaffold support.
  `rich_text:install` generates shared storage and installs assets.
- Editable `RichText` records with independent save/update/destroy, signed Trix
  file uploads, image galleries, embed preloading, and post-commit attachment
  cleanup. Uploads use session-bound form capabilities and CSRF protection.
- Rich-text `encrypted`, `strict_loading`, and `store_if_blank` options and
  `Blob.purge_unattached()` for abandoned-upload cleanup. `rich_text:install --force`
  updates app-owned editor assets after reviewing customizations.
- Model-level `encrypts(...)` declarations with randomized encryption,
  deterministic equality lookups, lowercase normalization, filtered inspection,
  encrypted fixtures, and explicit data/key migration. Rich text shares the same
  encryption service. `db:encryption:init` generates dedicated credentials keys;
  `config.encryption` configures model and rich-text encryption.

## 0.8.0 - 2026-10-22

### Breaking changes

- Replace standalone `params` imports with instance-owned `self.params` in
  controllers and mailers. Controller templates retain `params`.
- Replace imported `render`, `respond`, `redirect_to`, and `head` with
  `self.render(...)`, `self.respond_to(...)`, `self.redirect_to(...)`, and
  `self.head(...)`.
- Responses are tracked without requiring a return value. Preparing a response
  in a before callback halts the chain; preparing a second raises
  `DoubleRenderError`. Implicit rendering precedes around cleanup and after
  callbacks. Response metadata is always available; use `self.performed` to
  distinguish a prepared response from header/status changes.
- Rename numericality's `allow_nil` option to `allow_none`; validation behavior
  is unchanged and the old name is removed.
- Declared `has_many` collections now expose an association API over SQLAlchemy's
  collection storage. Native `relationship()` collections remain unchanged.

### Added

- Parameterized mailers: `Mailer.with_params(...).action()` supplies isolated
  action and callback inputs through `self.params`.
- Queued mailer assigns support saved models, including nested lists, tuples,
  and dictionaries. Models reload at delivery; unsaved assigns raise
  `SerializationError`, and missing records raise `DeserializationError`.
  Actions still run immediately, capturing recipients and subjects.
- Association-scoped `new()`, `create()`, and `where(...).first_or_create()`;
  scoped queries also support creation from keyword equality filters.
- Saved-change inspection through `saved_changes`, `saved_change_to_attribute()`,
  and `attribute_before_last_save()`, including commit callbacks.
- Named controller methods as `rate_limit(..., with_="_handler")` handlers.

### Fixed

- Commit callbacks can query associations and save records after the transaction
  closes. Rolled-back savepoints preserve the outer save's commit history.
- Content negotiation considers only offered formats and returns 406 when none
  are acceptable, rather than falling back to HTML.
- Generated authentication uses instance-bound response helpers and rate-limit
  handlers. Password-reset mail queues serializable assigns with absolute links;
  generated test settings provide `localhost` for absolute URL generation.
- Simplify the getting-started restock workflow and clarify that inventory
  defaults require editing only the generated column, not replacing `upgrade()`.

## 0.7.0 - 2026-10-22

### Breaking changes

- Replace `@rules(...)` with explicitly imported declarations called directly in
  model, controller, mailer, or mixin class bodies. Repeated declarations preserve
  source order and binding remains deferred. Custom factories use `@declaration`;
  calls in unsupported scopes raise `ProgrammerError` rather than being discarded.

- Resource helpers generate slashless canonical paths and `.json` suffixes, with
  direct optional-trailing-slash recognition (no redirects or body replay).
  Nested routes preserve the parent's member parameter and bind separate ancestor
  parameters. Conventional collection/member helpers replace action-specific
  resource helper aliases and work in templates as well as Python. Missing or
  conflicting bindings/helper names fail diagnostically.
- Model-backed forms infer PATCH for persisted records, honor explicit URLs and
  methods independently, and support nested model sequences and explicit field
  scope. `button_to` accepts URLs/records/sequences and a keyword-only `method`;
  defaults are POST for URLs/new records and PATCH for persisted records. Unsafe
  methods use browser-valid POST forms with hidden overrides; GET forms omit CSRF.
- POST method overrides apply to all routes, including native Flask endpoints.
  Form `_method` takes precedence over the header; query parameters cannot change
  the method. Routing and CSRF protection use the effective method. Unsupported
  operations on framework routes return 404.

- Standalone model saves, updates, creation, and destruction now commit before
  returning, including associated writes. Use `Model.transaction()` to group
  operations; nested blocks join by default and `requires_new=True` requests a
  savepoint. Context teardown no longer commits unfinished native writes. Attachment
  uploads and commit hooks follow the actual operation/outer transaction boundary.
- Replace reflected row-wrapper models with lazy native mappings of application
  classes. Association declarations and staged scalar edits remain model-owned;
  native/facade queries now share session identity. Native collections replace
  custom `Relation` wrappers; create children through their model's `create()`.
- Migrations own schema changes. Successful migration, preparation, and rollback
  regenerate a committed `db/schema.py` snapshot; `db:schema:dump` refreshes it
  independently. Imports do not require snapshots or special migration startup.
  Existing apps with `app/schema.py` should run `flask db:schema:dump`, remove
  the old snapshot, and restart servers/workers.
- Model queries are immutable. Native ORM callers can
  explicitly prepare mappings and publish staged attributes with `prepare()` and
  `apply_changes()`. Native inspection tracks published state, not unsaved input.
- Remove the duplicate `Field.as_primitive()` / `from_column_type()` casting API.
  Generator field names now select native SQLAlchemy type factories. Model casting
  retains before-type-cast input; empty boolean strings cast to null, and numericality
  validation checks the original input.
- Initialize simple literal defaults from the generated server-default metadata;
  leave functions/computed values to the server. Explicit non-primary-key nulls do
  not accidentally reapply server defaults. See [Models](docs/models/index.md).

### Fixed

- Standard session-resource logout, generated scaffold deletion, and nested child
  model forms work with CSRF enabled without JavaScript or application-owned route
  workarounds. Generators and the getting-started guide use those workflows.
- Uncountable resource collections use `_index` helpers consistently with model
  form/button inference. Individually declared verbs can share a controller
  action, and structured input cannot replace route bindings.

## 0.6.0 - 2026-10-15

### Added

- Asset helpers and `assets:precompile`, using Flask's native static
  endpoint. Generated layouts and Docker builds integrate assets.
  See [Assets](docs/other/assets.md).

### Changed

- Assigning `None` to a boolean column now preserves null instead of casting it
  to `False`. Assign `False` explicitly for false values. Existing stored values
  are not rewritten; other non-null boolean conversions are unchanged.
- `params.expect` rejects null, blank, and empty required roots, including
  dictionaries with no permitted attributes after filtering. Required scalar
  `False` and numeric zero remain valid; Python schema syntax and return shapes
  are unchanged.

### Fixed

- Model field casting preserves `None` for all supported column types. String
  and text attributes no longer become `"None"`, so presence validation rejects
  explicit nulls correctly. Nullable numeric and JSON attributes accept nulls
  without conversion errors. JSON serialization retains its existing JSON-null
  versus SQL-NULL distinction, and database constraints remain enforced.
- Strong-parameter allowlists now permit omitted nested attributes, including
  fields in nested dictionaries and arrays of dictionaries. Partial updates can
  use a fixed allowlist without requiring unchanged fields. Omitted attributes
  are not filled with defaults; supplied values still undergo type checks.
- Generated scaffold controllers use fixed upload allowlists rather than
  selecting permitted attachment fields dynamically from submitted parameters.

## 0.5.0 - 2026-10-14

### Changed

- Default `flaskteroids new` installs app dependencies with uv, creates the app's
  lock, bootstraps migrations without app boot, and prepares its selected database.
  `--skip-install` defers installation/preparation to repeatable `bin/setup`.
- Metadata uses the validated destination basename and a generator-compatible
  minor-line framework constraint. Prerelease/development generators pin exactly;
  unpublished candidates require an explicitly configured source before installation.
- Generated `bin/flask` selects the app interpreter without activation or runtime uv.
  Setup uses `uv sync` and public `db:prepare`, honoring environment/DB overrides and
  preserving records/credentials. CI and Docker require a current committed app lock.
- Framework test commands explicitly succeed for no tests, including empty filters.
  Direct pytest stays strict and all other failures remain nonzero. New apps include
  a health integration test and locked, pristine-app green CI.
- Default Docker copies a locked environment across compatible Python stages, runs
  unprivileged, and prepares before default web startup. Other commands bypass
  preparation. Fleets must coordinate one release step. Runtime keys, external
  services/drivers and persistent writable storage remain explicit requirements.
- Removed malformed Kamal output, unsafe automatic SSH deployment, duplicate release
  script and falsely successful assets placeholder. Kamal integration is deferred
  pending verified version/configuration/secret/release wiring, not rejected.
- Substantial generated file bodies now use packaged templates, including hidden CI
  and scripts. Generation and required-script chmod failures return nonzero status.

Older apps are not silently changed. Deliberately review/copy the new helpers,
Docker and CI files, add a compatible constraint and `[tool.uv] package = false`,
run setup and commit the app lock. Retain credentials/migrations and manually
review/remove old deployment examples. Regeneration can overwrite files.

- Renamed the misspelled `flaskteroids.model.LenghtConfig` validation configuration
  type to `LengthConfig`; the old spelling has been removed.

- Model internals now have focused validation, authentication, association, and
  query modules; model APIs remain available from `flaskteroids.model`.
- Legacy discovery imports from `flaskteroids.extensions.utils` now use the
  canonical discovery functions. Missing optional packages remain optional, but
  broken package dependencies propagate instead of being silently ignored.
- Unknown model attributes now raise `AttributeError` instead of being ignored.
  Use class defaults, properties with setters, or private attributes for temporary values.
- Belongs-to assignments accept the target model or `None`; wrong types raise
  `TypeError`. Has-many collections reject direct replacement; use `create()` to add records.
- Removed `flaskteroids.registry.get`. Custom rules now use application-owned
  class attributes and must prepare classes without capturing app resources.
  Inherited rules visit each ancestor once, base-first in left-to-right order;
  separately declared occurrences still run separately against each child.
- Shell model methods no longer auto-commit. The shell exposes `session` for
  explicit commit and rollback; normal app-context exit still commits.
- Default in-memory caches and rate-limit counters are app-local. Calls outside
  Flask use a separate process-local store. Model use and job enqueueing require
  an active app context and registration in that app.
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

- Missing optional packages remain optional; broken imports now stop setup
  instead of being silently skipped.
- Setup errors identify affected models and associations without hiding the
  underlying failure. Tables without a primary key now fail clearly during setup.
- Shared classes retain independent model mappings, associations, job adapters,
  mail delivery, and storage across applications. Repeated action preparation
  and successful app setup no longer stack callbacks, wrappers, or routes.
- Nested app contexts use independent database sessions and restore the outer
  session. Teardown closes its session even when commit fails.
- Apps with empty or partial schemas boot without borrowing another app's model
  mappings. Missing tables fail with migration guidance when used.
- Association creation saves supplied fields and keeps inverse collections free
  of duplicate entries. Loaded secure-password models can update unrelated fields.
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

