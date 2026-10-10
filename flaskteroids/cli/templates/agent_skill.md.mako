---
name: using-flaskteroids
description: Use when building or modifying this Flaskteroids application. Load the installed framework's version-matched instructions first.
---

# Using Flaskteroids

Before working on this application's Flaskteroids code:

1. Respect the application's local instructions and use its configured environment,
   not a globally installed or unrelated Flaskteroids version.
2. From the application root, run:

   ```sh
   flaskteroids agent-skills path
   ```

   For projects managed with uv, use:

   ```sh
   uv run flaskteroids agent-skills path
   ```

3. The command prints the absolute directory containing the installed package's
   skills. Open `using-flaskteroids/SKILL.md` inside that returned directory,
   not this application-local loader. Read that file completely and apply its
   instructions before implementing changes, including its framework-first API
   requirements.

If the command is unavailable, check the application's dependency installation
and environment first. Report any remaining blocker rather than silently using
another version's instructions. Resolve and reread the package skill after changing
the installed Flaskteroids version; do not hardcode its installation path or copy
its guidance into this loader.
