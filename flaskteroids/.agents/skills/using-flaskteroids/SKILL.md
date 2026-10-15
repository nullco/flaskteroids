---
name: using-flaskteroids
description: Use when building or modifying a Flaskteroids application.
---

# Using Flaskteroids

- Work in the application's environment and respect its local instructions.
- Start with `flaskteroids --help` and, from the application root, `bin/flask --help`.
  Follow the command groups and read `--help` for each command relevant to the
  task. Installed command help is the source of truth for syntax and behavior.
- Prefer existing commands over building from scratch. Use generators for
  supported application components and framework commands for migrations,
  testing, and credentials. Write scaffolding or tooling manually only after
  checking that no existing command covers the need.
- Inspect existing files before generating; commands may overwrite files.
  Review generated changes, follow the application's MVC conventions and base
  classes, and use public framework APIs rather than recreating internals.
- Inspect a comparable existing component before implementing a new one. Follow
  local patterns rather than imposing generic Flask patterns on the application.
- Keep changes scoped to the task. Generated files are application-owned code,
  not disposable scaffolding. Do not regenerate or clean up unrelated files as
  part of a feature.
- Add or update tests with behavior changes and run the relevant test commands.
  Never commit encryption keys or expose plaintext credentials.

## Generation, setup, and tests

- `flaskteroids new` installs app dependencies, creates its lock, and prepares
  development SQLite by default. `--skip-install` explicitly defers this to
  `bin/setup`; it still writes Docker and migration resources. Requires Git,
  Bash/POSIX and (unless skipped) uv. Never claim skipped installation is runnable.
- Use `bin/flask` for app commands without activation; existing Flask/uv syntax
  remains supported. Use `bin/setup` for a fresh checkout or changed dependencies.
  Commit the app-owned `uv.lock`; CI and Docker use `uv sync --locked`.
- Setup honors explicit FLASK_ENV/DATABASE_URL and prepares that selected database.
  `bin/flask db:prepare` applies existing migrations without resets, repairs,
  external DB creation, or seeds. `db:init` stays strict. Restart after migrations.
- `bin/flask test` and `bin/flask test:system` report empty selections as success;
  direct pytest is strict. Real failures stay nonzero. Install Chromium explicitly
  when system tests exist; an empty system suite needs no browser. Test adapters
  need no broker, SMTP or external storage.
- Use `stylesheet_link_tag("application")` and `asset_path("logo.png")` for
  `app/assets`. Run `bin/flask assets:precompile` during production builds
  (included in Docker). See [Assets](https://nullco.github.io/flaskteroids/other/assets/)
  for paths, CSS references, configuration, and limits.
- Default Docker web startup prepares before workers. Coordinate a single release
  step for fleets; runtime keys and persistent storage are explicit prerequisites.
  Kamal integration is deferred, not replaced by unsafe remote-deployment examples.

## Application context

- Use models and enqueue jobs inside an application context. Requests and jobs
  already have one. Keep records, queries, and files in the app that created them.
- Custom rules set class attributes. Put database queries and work that needs an
  application in actions, callbacks, or initializers.
- In `bin/flask shell`, call model `save()` to validate/publish staged scalar input,
  then `session.commit()` to commit published work. Normal context exit also commits
  published work, not unsaved staged assignments. Roll back failed unit-of-work
  operations explicitly; use `discard_changes()` or `reload()` to discard staged input.
- Run `bin/flask db:prepare` to apply migrations and regenerate `app/schema.py`,
  then restart. Commit the snapshot, never edit it by hand. `db:schema:dump` refreshes
  it independently. Model declarations import without it; construction, queries,
  and mapped fields need it. All commands use normal application initialization.
- Fix broken imports in model, controller, mailer, and job packages; don't suppress them.

## Preserve application behavior during UI changes

Treat existing layouts as application infrastructure, not disposable starter
markup. A visual redesign does not imply permission to replace the frontend
stack or remove existing behavior.

- Read the current layout, affected templates, and referenced assets before
  editing. Modify existing templates rather than replacing them wholesale.
- Preserve Turbo, template inheritance blocks, shared scripts, stylesheets,
  and security-related markup unless the task explicitly requires changing
  them. Their presence is not evidence that they are unused.
- Use the existing layout blocks for page-specific content and assets.
  Make shared layout changes when needed, but preserve its existing contracts.
- Do not introduce another frontend framework or disable Turbo just to make
  new UI code work. Check compatibility with the application's existing
  navigation and form behavior first.
- When a requested change requires removing or replacing an existing
  integration, explain the behavior affected and confirm the scope first.

For UI changes, verify relevant behavior as well as appearance. When Turbo
is enabled, check navigation and form submissions through Turbo, not only
a fresh page load.

## Framework-first implementation

Always use public Flaskteroids abstractions when they cover the task. This is a
requirement, not merely a stylistic preference: do not bypass the framework with
dependency internals or introduce a parallel implementation of a supported feature.

- Use the application's abstract `ApplicationModel` base, Rails-like queries,
  and `@rules(belongs_to(...), has_many(...), ...)` declarations for routine work.
  Models themselves are native SQLAlchemy-mapped objects, prepared lazily from
  the generated snapshot. Native statements/options are supported on those same
  objects for complex queries; `Model.prepare()` explicitly prepares bare native
  class APIs without database I/O. Do not introduce separate mapped row classes.
- Unknown public model attributes raise `AttributeError`. For temporary values,
  declare class defaults or properties with setters, or use private attributes.
  A type annotation alone isn't enough. Don't overwrite framework methods or state.
- Assign belongs-to associations their target model or `None`; framework saves
  validate new associated objects. Collections are native: use append/remove or
  replacement, and `Child.create(parent=parent, ...)`, not `parent.children.create()`.
  Native relationship mutations are not scalar staging. A rejected scalar update
  retains its input and does not undo a prior collection mutation. `apply_changes()`
  explicitly publishes staged scalars for native writes, bypassing validation/callbacks.
- Use application controllers, `config/routes.py`, resourceful routing, strong
  parameters (`params.expect`), and framework response helpers instead of standalone
  Flask routes or manually rebuilding the request pipeline. `render(json=value,
  status=...)` supports ordinary JSON values, models, queries, and model errors.
  Errors serialize as full-message lists; use status 422 for validation failures.
  Only `None` returned by an action triggers implicit template rendering.
- `params.expect(post=[...])` requires the outer parameter but permits optional
  nested attributes. Keep fixed allowlists for partial updates, including uploads;
  omitted attributes remain unchanged. Use model validations for required fields.
  Missing/null/empty roots and blank required scalars are rejected.
- Declare controller callbacks through `before_action`, `around_action`, and
  `after_action`. Around callbacks are generators that yield once and unwind in
  reverse order, including on failures. Cleanup resumes them normally rather than
  throwing the action exception into them. After callbacks require successful
  action execution and cleanup. Do not use after callbacks for failure cleanup.
- Use attachment declarations, `config/storage.yml`, and `attachments:install`
  for file uploads rather than independent storage plumbing.
  Model attachments upload after commit. Use `blob_path` or `blob_url` for
  permanent application links; `blob.url()` returns an expiring service URL.
  Signed links grant access by default. For private files, use
  an authorization callback with proxy routing, or custom authorized controllers.
  Direct service URLs bypass the callback until they expire.
- Use `form_with`, field helpers, and framework CSRF protection instead of hand-built
  equivalents where helpers support the required behavior. Helpers escape ordinary
  text and attributes. Use `Markup` only for trusted HTML, never for user input.
  Links allow relative, HTTP(S), mailto, and tel URLs; form actions allow relative
  and HTTP(S) URLs. Validate user-supplied destination hosts separately.
- Model JSON responses include database columns and pending column changes, but
  omit authentication secrets and virtual fields. Customize the existing `__json__()`
  protocol to select response attributes, preferably starting with `super().__json__()`.
  Do not add passwords, digests, confirmations, or reset tokens to ordinary responses.
  Model-backed forms obtain values independently of response serialization.
- Use Flaskteroids jobs and mailers (`perform_later`, `deliver_later`) rather than
  registering raw Celery tasks or managing Celery dispatch directly.
- Use framework configuration, credentials, migrations, and testing abstractions
  rather than configuring or bootstrapping the underlying dependencies separately.

Before reaching for a lower-level dependency API:

1. Check installed command help, existing application code, and public Flaskteroids
   APIs for the supported approach. Do not assume a feature is absent.
2. Use the framework abstraction if it supports the behavior, even when a dependency
   API is more familiar or shorter.
3. Only use a lower-level API when there is a concrete gap. Explain the limitation
   and why the fallback is necessary, keep it narrow, and preserve framework
   lifecycle hooks and security protections. Do not access private dependency or
   framework internals to work around a missing public API.

Documented dependency primitives used within framework APIs are allowed—for example,
SQLAlchemy expressions passed to `Model.where`, Flask's `url_for`, or Jinja template
syntax. The requirement is to use Flaskteroids as the integration layer, not to ban
all dependency imports. When reviewing changes, check for unnecessary raw Flask,
SQLAlchemy, or Celery integration and replace it with supported framework APIs.
