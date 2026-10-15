# Application integration tests

These tests create an app, generate features, and exercise them through its normal
Flask commands. The same tests cover startup, migrations, CRUD, associations,
fixtures, transactions, and mail.

Run locally with SQLite:

```sh
uv run pytest tests/integration -v
```

To try another backend, start a disposable server and set the application's usual
`DATABASE_URL`:

```sh
DATABASE_URL='postgresql+psycopg://postgres:password@localhost/flaskteroids_integration' \
  uv run --locked --group integration pytest tests/integration -v
```

For MySQL, use a `mysql+pymysql://` URL instead. CI runs these same tests in a
PostgreSQL/MySQL matrix; the Python-version matrix uses SQLite.

**Use only a fresh, disposable database.** Tests create tables and write/delete
records, then roll back their migrations. The account needs permission to create
and migrate the database. A configured but unavailable database fails the tests.
