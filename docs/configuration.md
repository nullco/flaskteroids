# Configuration

Configure application-wide settings in `config/application.py` and override them in `config/environments/`. Database settings live in `config/database.yml`. Store secrets in encrypted credentials and use initializers to configure external libraries during boot.

## Application boot

A generated application boots through `config/environment.py`:

```python
from config.application import Application

application = Application.initialize()
```

`wsgi.py` exposes that application to Flask and WSGI servers:

```python
from config.environment import application as app
```

Application-wide configuration lives in `config/application.py`:

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
with application.app_context():
    user = User.find(1)
    MyJob().perform_later(user_id=user.id)
```

Each context has its own database session. Normal exit commits pending changes;
an exception rolls them back. You can also call `session.commit()` or
`session.rollback()` explicitly.

If you use multiple applications, keep records, queries, and files in the app
that created them. Restart the application after changing its database schema.

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

Read environment variables explicitly in configuration code. Flaskteroids does not map arbitrary SMTP, job, or application environment variables to settings.

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
  adapter: postgresql
  database: my_application_production
```

Values can reference environment variables with `${NAME}` or `${NAME:-default}`:

```yaml
production:
  adapter: postgresql
  database: ${DATABASE_NAME}
  username: ${DATABASE_USER:-postgres}
  password: ${DATABASE_PASSWORD}
```

`DATABASE_URL` uses the following precedence:

- When present, it overrides connection values from the selected environment.
- An explicit `url` entry in `database.yml` takes precedence over `DATABASE_URL`.
- Without either URL, Flaskteroids constructs the connection URL from the selected settings.

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

Files in `config/initializers/*.py` run once during application initialization, in filename order and inside the application context. Use initializers to configure external libraries:

```python
# config/initializers/payments.py
from flaskteroids import application
from payments import Client

application.extensions['payments'] = Client(
    api_key=application.credentials.payments.api_key
)
```

## Boot order

Flaskteroids initializes an application in this order:

1. Select the environment.
2. Apply `config/application.py` configuration.
3. Apply `config/environments/<environment>.py`.
4. Load `config/database.yml` and credentials.
5. Initialize framework components.
6. Run files in `config/initializers/`.
7. Finish route and application setup.
