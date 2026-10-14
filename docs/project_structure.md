# Project structure

`flaskteroids new` generates this application layout. The tree shows the main directories and configuration files:

```text
my_project/
├── app/
│   ├── assets/
│   ├── controllers/
│   ├── helpers/
│   ├── models/
│   ├── mailers/
│   ├── views/
│   └── jobs/
├── bin/                 # flask, setup, release, docker-entrypoint
├── deploy/README.md
├── Dockerfile
├── .dockerignore
├── config/
│   ├── environments/
│   │   ├── development.py
│   │   ├── test.py
│   │   └── production.py
│   ├── initializers/
│   ├── application.py
│   ├── boot.py
│   ├── credentials.yml.enc
│   ├── database.yml
│   ├── environment.py
│   └── routes.py
├── db/
│   └── migrate/
├── public/assets/       # fingerprinted build output and manifest; not committed
├── storage/
├── test/
├── pyproject.toml
├── uv.lock              # created by installation; commit this
├── jobs.py
├── Procfile
└── wsgi.py
```

| Path | Contents |
| --- | --- |
| `app/assets` | Source stylesheets/images, served automatically in development/test. |
| `public/assets` | Fingerprinted production assets and manifest, created by precompilation. |
| `app/controllers` | Request-handling actions. |
| `app/helpers` | Template helpers. |
| `app/models` | Database-backed models and business logic. |
| `app/views` | Jinja templates. |
| `app/mailers` | Email actions. |
| `app/jobs` | Background jobs. |
| `config/application.py` | Application-wide configuration. |
| `config/environments` | Environment-specific overrides. |
| `config/initializers` | Library configuration that runs during boot. |
| `config/database.yml` | Database connections by environment. |
| `config/credentials.yml.enc` | Encrypted application secrets. |
| `config/routes.py` | Application routes. |
| `db/migrate` | Database migrations. |
| `storage` | Local database files and uploads; keep persistent in containers. |
| `bin/flask` | App-interpreter command launcher. |
| `bin/setup` | Repeatable uv sync and selected-database preparation. |
| `bin/release migrate` | Explicit preparation for a coordinated release step. |
| `bin/docker-entrypoint` | Prepare before default Gunicorn web startup only. |
| `uv.lock` | App-owned exact resolution; setup creates/updates, CI/builds require freshness. |
| `deploy/README.md` | Docker/runtime secrets/storage instructions; no automatic SSH deployment. |
| `Procfile` | Platform example requiring PORT and a reachable worker broker. |
| `test` | Tests and YAML fixtures. |

Default generation installs and prepares; `--skip-install` defers that work to
`bin/setup`. Bash/POSIX, Git, and uv are setup prerequisites. `db:init` initializes
only migration files and stays strict; `db:prepare` applies existing migrations
without resetting data, seeding, repairing files, or creating external databases.
The generated app is a non-package uv project, not a distributable library.

See [Assets](other/assets.md) for helpers and build configuration.

See [Configuration](configuration.md) for the boot process, environments, credentials, and database setting precedence.
