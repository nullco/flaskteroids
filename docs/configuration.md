# Configuration

Start with the generated defaults and change settings as your application needs
them. Run the commands in this guide from your application directory.

| What you want to configure | Where to put it |
| --- | --- |
| Settings shared by every environment | `config/application.py` |
| Development, test, or production overrides | `config/environments/` |
| Database connections | `config/database.yml` |
| API keys and other secrets | Encrypted credentials |
| External library setup | `config/initializers/` |

Environment settings are applied after application-wide settings, so they can
override the shared defaults.

## Application settings

Start with `config/application.py` for settings shared by every environment:

```python
from flaskteroids.application import Application as FlaskteroidsApplication
from config.boot import ROOT


class Application(FlaskteroidsApplication):
    root = ROOT

    def configure(self, config):
        config.load_defaults("0.1")
        config.x.payments.provider = "stripe"
```

`config.load_defaults()` selects the framework defaults for a version. Updating
Flaskteroids does not change this choice automatically. To adopt newer defaults,
change the version passed to `load_defaults()`.

## Template helpers

Application helpers are discovered in `app.helpers` and included in controller
views by default:

```python
config.paths.helpers = "app.helpers"
config.action_controller.include_all_helpers = True
```

Set `include_all_helpers = False` to include only `ApplicationHelper`,
conventionally matching controller helpers, and explicit `helper(...)`
selections. See [application helpers](views/index.md#application-helpers) for
inheritance, naming, mailer boundaries, and development reloading.

## Internationalization

Translation catalogs live under `config/locales` by default:

```python
config.i18n.default_locale = "en"
config.i18n.available_locales = ["en", "es"]
config.i18n.fallbacks = False
config.i18n.raise_on_missing_translations = False
config.i18n.pluralization_rules = {}
config.paths.locales = "config/locales"
```

Locale selection is application policy. Use `with_locale(...)` in an around
callback rather than changing process-global state. See
[Internationalization](other/internationalization.md) for catalogs and helpers.

## Request limits

Set request limits in `configure`, rather than in request or controller callbacks:

```python
config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # Total request body: 16 MiB
config["MAX_FORM_MEMORY_SIZE"] = 500_000         # Each multipart text field
config["MAX_FORM_PARTS"] = 1_000                # Multipart fields and files
```

Requests that exceed these limits are rejected with **413 Content Too Large**.

## Using models and jobs in scripts

Requests and jobs run inside an application context. In scripts, open one before
using models or enqueueing jobs:

```python
from app.jobs.my_job import MyJob
from app.models.user import User
from config.environment import application

with application.app_context():
    user = User.find(1)
    MyJob().perform_later(user_id=user.id)
```

An application context provides configuration and a database session; **it is not
a transaction**. A standalone model save commits before returning. To group writes,
use `with Model.transaction():`; an exception escaping the block rolls them back.

When the context ends, it closes the session and rolls back unfinished work. It
does not undo earlier standalone commits. Native SQLAlchemy writes require an
explicit commit or transaction.
See [Models](models/index.md#assignment-validation-and-persistence).

## Environments

Flaskteroids selects the environment in this order:

1. The explicit `environment=` argument to `Application.initialize()`.
2. `FLASKTEROIDS_ENV`.
3. `development`.

`FLASKTEROIDS_ENV` selects Flaskteroids configuration, not Flask's debugger.
Use `bin/flask run --debug` to enable the debugger.

Framework-provided environment variables use the `FLASKTEROIDS_` prefix, including
`FLASKTEROIDS_DATABASE_URL`, `FLASKTEROIDS_SECRET_KEY_BASE`,
`FLASKTEROIDS_MASTER_KEY`, `FLASKTEROIDS_ATTACHMENTS_SERVICE`, and
`FLASKTEROIDS_ENCRYPTION_*`. The prefix applies only to environment variables:
Python settings such as `config.secret_key_base` and `config.encryption.primary_key`,
and credential names such as `secret_key_base` and `encryption`, remain unprefixed.
Dependency-owned variables such as Flask's `FLASK_APP` and Celery's
`CELERY_BROKER_URL` retain their native names.

Put environment-specific overrides in the matching file. For example:

```python
# config/environments/production.py
import os


def configure(config):
    config.eager_load = True
    config.consider_all_requests_local = False
    config.require_master_key = True
    config.action_mailer.perform_deliveries = True
    config.jobs.broker_url = os.environ.get(
        "CELERY_BROKER_URL", config.jobs.broker_url
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
  url: ${FLASKTEROIDS_DATABASE_URL}
```

The generated app uses SQLite for development and tests. For another database,
install its driver and set `FLASKTEROIDS_DATABASE_URL`:

For PostgreSQL:

```sh
uv add 'psycopg[binary]'
export FLASKTEROIDS_DATABASE_URL='postgresql+psycopg://app:password@localhost/my_app'
```

Or for MySQL:

```sh
uv add 'PyMySQL[rsa]'
export FLASKTEROIDS_DATABASE_URL='mysql+pymysql://app:password@localhost/my_app'
```

Use `${NAME}` in YAML to read an environment variable, or `${NAME:-default}` to
supply a fallback. Connection settings are chosen in this order:

1. An explicit `url` in `database.yml`.
2. `FLASKTEROIDS_DATABASE_URL`.
3. Individual settings such as `adapter`, `database`, `username`, and `password`.

## Preparing for deployment

On a fresh checkout, run `bin/setup` to install dependencies and prepare the
database. Before deploying database changes, prepare your production environment:

```sh
FLASKTEROIDS_ENV=production bin/flask db:prepare
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

Credentials let you keep API keys and other secrets in an encrypted YAML file.
The shared file is `config/credentials.yml.enc`; its local key is
`config/master.key`. Encryption uses AES-256-GCM.

**Commit the encrypted file, never the key.** Generated Git and container ignore
files already exclude the key. In production, supply it through
`FLASKTEROIDS_MASTER_KEY` rather than putting it in your image.

Open the editor to add secrets:

```sh
bin/flask credentials:edit
```

For example, add this YAML in the editor:

```yaml
payments:
  api_key: your-secret-key
```

To inspect decrypted values, run `bin/flask credentials:show`. Its output is
plaintext: do not copy it into logs or issue reports.

### Separate credentials for each environment

Use `--environment` to edit or inspect an environment-specific file:

```sh
bin/flask credentials:edit --environment production
bin/flask credentials:show --environment production
```

The edit command creates these files if needed:

```text
config/credentials/production.yml.enc
config/credentials/production.key
```

Environment-specific credentials **replace**, rather than merge with, shared
credentials. Include every secret that environment needs. The key is read from
`FLASKTEROIDS_MASTER_KEY` first, then the corresponding key file.

### Read credentials in Python

Credentials are available through the application:

```python
application.credentials.secret_key_base
application.credentials.payments.api_key
application.credentials["payments"]["api_key"]
```

In production, set `config.require_master_key = True` so startup fails if
credentials cannot be decrypted.

The keys have different purposes:

| Key | Purpose |
| --- | --- |
| Credentials master key | Decrypt the credentials file |
| `secret_key_base` | Sign sessions, CSRF tokens, and password-reset tokens |
| `encryption.primary_key` / `encryption.deterministic_key` | Encrypt model attributes and rich-text bodies |

Do not reuse the master or signing key for model data. See
[Attribute encryption](models/encryption.md) to set up encrypted attributes.

## Initializers

Use initializers for setup that should run once during application startup,
such as creating an external service client:

```python
# config/initializers/payments.py
from flaskteroids import application
from payments import Client

application.extensions["payments"] = Client(
    api_key=application.credentials.payments.api_key
)
```

Keep database queries out of initializers when possible. Query from an action,
job, or function when the data is needed, so database setup can run before tables
exist.
