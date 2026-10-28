# Application integration tests

These tests create an app, generate features, and exercise them through its normal
Flask commands. The same tests cover startup, migrations, CRUD, associations,
fixtures, transactions, and mail.

Run locally with SQLite:

```sh
uv run pytest tests/integration -v
```

To try another backend, start a disposable server and set the application's usual
`FLASKTEROIDS_DATABASE_URL`:

```sh
FLASKTEROIDS_DATABASE_URL='postgresql+psycopg://postgres:password@localhost/flaskteroids_integration' \
  uv run --locked --group integration pytest tests/integration -v
```

For MySQL, use a `mysql+pymysql://` URL instead. CI runs these same tests in a
PostgreSQL/MySQL matrix; the Python-version matrix uses SQLite.

**Use only a fresh, disposable database.** Tests create tables and write/delete
records, then roll back their migrations. The account needs permission to create
and migrate the database. A configured but unavailable database fails the tests.

## Routing/form correctness

`test_routing_correctness.py` generates a catalog plus authentication and nested
subscriptions. It exercises actual/form/header logout, CSRF rejection, child
create/update and validation redisplay, and raw numeric input through generated
controllers/templates. It also covers automatically loaded presentation helpers,
controller authentication delegates, and helper discovery after a process restart.
Shared generation/subprocess fixtures live in
`tests/generated_application.py`; executable scenarios and application edits are
ordinary source files. Setup-only CLI commands are batched in a builder process;
runtime and restart contracts still run in fresh processes. The logout/CSRF
matrix runs as independent cases in one generated pytest session. Default SQLite
databases belong to temporary applications and need no downgrade cleanup. An
explicit `FLASKTEROIDS_DATABASE_URL`, including a shared SQLite URL, retains
migration cleanup, batched in one process. Dedicated reversal tests still check
migration downgrade behavior. No known-failure markers remain.

Browser workflows live separately in `tests/system/test_routing_workflows.py`,
so the database-only integration job remains browser-free. They exercise generated
navigation, CRUD, nested forms, scaffold deletion, and normal session logout with
CSRF enabled and JavaScript both disabled/enabled. External Turbo loading is
blocked: remote/Turbo behavior is outside this correctness package.

`tests/system/test_turbo_workflows.py` covers generated Turbo Frame and HTTP Stream
browser workflows using the fixture in `tests/integration/application/turbo`.
These browser tests run in the Python-version matrix, not the database-only jobs.

`tests/routing/` covers method override behavior, native route boundaries,
multipart uploads/limits, resource identities/helpers, and model form/button
inference. Method override inputs and expectations are ordinary Python test data
in `tests/routing/method_override_cases.py`. These suites test Flaskteroids and its
generated applications.
