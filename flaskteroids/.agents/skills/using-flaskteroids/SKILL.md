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
- Add or update tests with behavior changes and run the relevant test commands.
  Never commit encryption keys or expose plaintext credentials.
