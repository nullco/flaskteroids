# Configuration

Configure application-wide settings in `config/application.py` and override them in `config/environments/`. Database settings live in `config/database.yml`. Store secrets in encrypted credentials and use initializers to configure external libraries during boot.

## Application settings

Start with `config/application.py` for settings shared by every environment:

```python
from flaskteroids.application import Application as FlaskteroidsApplication
from config.boot import ROOT


class Application(FlaskteroidsApplication):
    root = ROOT

    def configure(self, config):
        config.load_defaults('0.1')
        config.x.payments.provider = 'stripe'
```

`config.load_defaults()` selects the framework defaults for the given version. Updating Flaskteroids does not change that selection. Change the version passed to `load_defaults()` to adopt newer defaults.

## Using models and jobs in scripts

Requests and jobs run inside an application context. In scripts, open one before
using models or enqueueing jobs:

```python
from config.environment import application

with application.app_context():
    user = User.find(1)
    MyJob().perform_later(user_id=user.id)
```

Each context has its own database session. Normal exit commits pending changes;
an exception rolls them back. You can also call `session.commit()` or
`session.rollback()` explicitly.

## Environments

Flaskteroids selects the environment in this order:

1. The explicit `environment=` argument to `Application.initialize()`.
2. `FLASK_ENV`.
3. `development`.

Flaskteroids reads `FLASK_ENV` to select configuration. Flask itself no longer uses this variable; use `flask run --debug` to enable its debugger.

Flaskteroids applies the selected file under `config/environments/` after application-wide configuration:

```python
# config/environments/production.py
import os


def configure(config):
    config.eager_load = True
    config.consider_all_requests_local = False
    config.require_master_key = True
    config.action_mailer.perform_deliveries = True
    config.active_job.broker_url = os.environ.get(
        'CELERY_BROKER_URL', config.active_job.broker_url
    )
```

The current environment is available from the application:

```python
application.env.name
application.env.development
application.env.test
application.env.production
```

Read other environment variables with `os.environ` in your configuration.

## Database configuration

Define database connections in `config/database.yml`:

```yaml
default: &default
  adapter: sqlite3
  pool: 5

development:
  <<: *default
  database: storage/development.sqlite3

test:
  <<: *default
  database: storage/test.sqlite3

production:
  url: ${DATABASE_URL}
```

The generated app uses SQLite for development and tests. For another database,
install its driver and set `DATABASE_URL`:

For PostgreSQL:

```sh
uv add 'psycopg[binary]'
export DATABASE_URL='postgresql+psycopg://app:password@localhost/my_app'
```

Or for MySQL:

```sh
uv add 'PyMySQL[rsa]'
export DATABASE_URL='mysql+pymysql://app:password@localhost/my_app'
```

YAML values can reference environment variables with `${NAME}` or
`${NAME:-default}`. Connection settings are chosen in this order:

1. An explicit `url` in `database.yml`.
2. `DATABASE_URL`.
3. Individual settings such as `adapter`, `database`, `username`, and `password`.

## Preparing for deployment

On a fresh checkout, run `bin/setup` to install dependencies and prepare the
database. Before deploying database changes, prepare your production environment:

```sh
FLASK_ENV=production bin/flask db:prepare
```

Start PostgreSQL or MySQL yourself and give the application permission to create
its database. If your host provisions it for you, use `db:migrate` to apply changes.
PostgreSQL preparation also needs access to the `postgres` database; choose another
with `config.database_tasks.maintenance_database` if your host requires it.
See [database commands](other/cli.md#database-preparation) for the everyday workflow.

Provide `FLASKTEROIDS_MASTER_KEY` when starting production so the app can read its
[encrypted credentials](#encrypted-credentials). Keep the key out of your image
and source control. SQLite databases and local uploads need persistent storage.

The generated Docker setup prepares the database before starting the web app.
When deploying several instances, arrange one release step for migrations instead
of letting every instance run them. Your generated `deploy/README.md` walks through
that setup.

## Encrypted credentials

Shared credentials live in `config/credentials.yml.enc`. Flaskteroids stores the local encryption key in `config/master.key`. Generated Git and container ignore files exclude the key.

Edit or display credentials with:

```sh
flask credentials:edit
flask credentials:show
```

Environment-specific credentials use the `--environment` option:

```sh
flask credentials:edit --environment production
flask credentials:show --environment production
```

These commands create:

```text
config/credentials/production.yml.enc
config/credentials/production.key
```

When environment-specific credentials exist, they replace the shared credentials for that environment. Flaskteroids reads the encryption key from `FLASKTEROIDS_MASTER_KEY` first, then from the corresponding key file.

Credentials are available through the application:

```python
application.credentials.secret_key_base
application.credentials.payments.api_key
application.credentials['payments']['api_key']
```

`secret_key_base` signs sessions, CSRF tokens, and password-reset tokens. Production should set `config.require_master_key = True` so boot fails when credentials cannot be decrypted.

## Initializers

Put startup configuration for external libraries in `config/initializers/`:

```python
# config/initializers/payments.py
from flaskteroids import application
from payments import Client

application.extensions['payments'] = Client(
    api_key=application.credentials.payments.api_key
)
```

Keep database queries out of initializers when possible. Query from an action,
job, or function when the data is needed, so database setup can run before tables
exist.
