---
name: using-flaskteroids
description: Use when building or modifying a Flaskteroids application.
---

# Using Flaskteroids

- Work in the application's environment and respect its local instructions.
- Start with `flaskteroids --help` and, from the application root, `flask --help`.
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
a fresh page load. Add regression coverage for behavior the change could break.

## Framework-first implementation

Always use public Flaskteroids abstractions when they cover the task. This is a
requirement, not merely a stylistic preference: do not bypass the framework with
dependency internals or introduce a parallel implementation of a supported feature.

- Use the application's base models and Flaskteroids querying, associations,
  validations, callbacks, and secure-password APIs instead of direct SQLAlchemy
  session management, mapped model classes, or relationship plumbing.
- Use application controllers, `config/routes.py`, resourceful routing, strong
  parameters (`params.expect`), and framework response helpers instead of standalone
  Flask routes or manually rebuilding the request pipeline.
- Use `form_with`, field helpers, and framework CSRF protection instead of hand-built
  equivalents where helpers support the required behavior.
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
