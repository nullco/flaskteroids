# ${project_title}

## Getting started

Default generation installs dependencies, writes uv.lock, and prepares development SQLite.
From a fresh checkout, or after changing dependencies, run `bin/setup`.
If you generated with `--skip-install`, run setup before running commands or building Docker.

```sh
bin/setup
bin/flask run
bin/flask test
<%block name="system_test_command">bin/flask test:system
</%block>\
bin/flask generate scaffold Post title:string content:text
bin/flask db:prepare
```

Start a background job worker in a separate terminal with `bin/jobs start`.
The worker and web server must use the same environment and broker settings.

Bash/POSIX, Git and uv are setup prerequisites. No shell activation is needed.
Commit `uv.lock`: setup uses `uv sync` without unconditional upgrades; CI and Docker
use `uv sync --locked` and fail on missing/stale locks. This app is not a Python package.
The framework constraint tracks the generator's minor line; prerelease/development
generators are pinned and require an explicitly configured source if unpublished.

Setup prepares the selected database; explicit `FLASKTEROIDS_ENV` and `FLASKTEROIDS_DATABASE_URL` are honored.
External databases must already exist, with their Python drivers added and locked.
Preparation retains records and credentials; it neither repairs migrations nor runs seeds.
Start servers/tests in a fresh process after migrating.

A health integration test is included. Framework test commands report empty selections as
successful with a no-tests message; direct pytest retains its strict exit status.
<%block name="browser_guidance">Install browsers explicitly when adding system tests:
`.venv/bin/playwright install chromium`.

Assets live in `app/assets` and are linked by the generated layout.
See [Assets](https://nullco.github.io/flaskteroids/other/assets/) for helpers,
build commands, and configuration.</%block>

Never commit `config/master.key` or plaintext secrets. Production requires the matching
`FLASKTEROIDS_MASTER_KEY`; `FLASKTEROIDS_SECRET_KEY_BASE` is not a substitute.
See [deploy/README.md](deploy/README.md) for Docker, persistent storage and release steps.
