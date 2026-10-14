# Command-line interface

Flaskteroids extends the Flask CLI with generators, database tasks, credentials
commands, and test runners. Generated apps lead with `bin/flask --help` and
`bin/flask <command> --help`: this launcher selects the app environment without
activation or runtime uv. Existing `flask ...` and `uv run flask ...` remain supported;
the examples below also work with `bin/flask`.

## Generation and setup

```sh
flaskteroids new my_app
cd my_app
bin/flask run
bin/flask test
bin/flask test:system
```

Generation requires Git, Bash/POSIX, and uv; installs app dependencies, creates its
lock, and prepares development SQLite by default. `--skip-install` skips sync,
lock resolution and database preparation, not Docker/migration resources. Run
`bin/setup` afterward. Names come from the destination basename, not its parents.
Generation may overwrite files and does not upgrade existing apps automatically.

`bin/setup` runs `uv sync` without unconditional upgrades and `bin/flask db:prepare`.
It defaults to development only when FLASK_ENV is unset and honors DATABASE_URL.
Commit `uv.lock`; CI and Docker use `uv sync --locked`. Prerelease/development
generators pin their exact version; unpublished versions need an explicit source.

## Asset precompilation

```sh
bin/flask assets:precompile
flaskteroids assets:precompile --root /path/to/app
```

Compile without application boot. See [Assets](assets.md) for build options
and production serving.

## Database preparation

```sh
bin/flask db:prepare
FLASK_ENV=test bin/flask db:prepare
bin/release migrate
```

Preparation verifies existing migration resources and applies pending migrations
using the selected database. It retains records/credentials and never repairs
files, seeds, or provisions remote databases. External DBs and their locked Python
drivers must already exist. `db:init` strictly initializes an absent/empty migration
directory and does not apply migrations. `db:migrate` remains supported. Restart
servers after schema changes; preparation does not rebuild shared model mappings.

## Shell

`flask shell` provides your models and `session`:

```python
user = User.create(name='Alice')
session.commit()
# Or discard pending work:
session.rollback()
```

Call `session.commit()` to save pending changes or `session.rollback()` to
discard them. Exiting the shell normally also commits pending changes.

## Credentials

Edit or inspect shared encrypted credentials:

```sh
flask credentials:edit
flask credentials:show
```

Use `--environment` for environment-specific credentials:

```sh
flask credentials:edit --environment production
```

See [Configuration](../configuration.md) for encryption keys and credential precedence.

## Generators

Use `flask generate` to create application components. Field arguments use `name:type` syntax. See [Fields](fields.md) for supported types.

### Migration

Generate a migration to create or drop a table, or add or remove columns. New tables include an auto-incrementing `id` and a `created_at` field by default.

#### Create a table

```sh
flask generate migration <CreateXXX> [field1:type ...]
```

For example:

```sh
flask generate migration CreateProducts name:string!
```

Use the plural table name after `Create`, without a `Table` suffix.

#### Add columns

```sh
flask generate migration <AddXXXToXXX> [field1:type ...]
flask generate migration AddPriceToProducts price:float
```

#### Remove columns

```sh
flask generate migration <RemoveXXXFromXXX> [field1 ...]
flask generate migration RemovePriceFromProducts price
```

#### Drop a table

```sh
flask generate migration <DropXXXX> [field1 ...]
flask generate migration DropProducts
```

Apply pending migrations with:

```sh
flask db:migrate
```

### Model

Generate a model and its database migration:

```sh
flask generate model <ModelName> [field1:type ...]
flask generate model User name:string email:string
```

### Controller

Generate a controller with the specified actions, a view for each action, and individual route entries:

```sh
flask generate controller <ControllerName> [action1 action2 ...]
flask generate controller Users index show
```

### Resource

Generate a model, its migration, an empty controller, and a resource route entry. You write the controller actions and views.

```sh
flask generate resource <ResourceName> [field1:type ...]
```

### Scaffold

Generate a model, its migration, a CRUD controller, views, and a resource route entry. The controller includes `index`, `show`, `new`, `edit`, `create`, `update`, and `destroy` actions.

```sh
flask generate scaffold <scaffold_name> [field1:type ...]
```

### Mailer

Generate a mailer with the specified actions:

```sh
flask generate mailer <MailerName> [action1 action2 ...]
flask generate mailer UserMailer welcome_email
```

### Authentication

```sh
flask generate authentication
```

Generate user and session models, login pages, and password management:

- A `User` model with `email` and `password_digest`.
- A `Session` model with `user_id`, `ip_address`, and `user_agent`.
- Controllers and views for login and password changes.
- Views and mailers for password resets.
- Routes for session and password management.

## Attachments

Set up file attachments:

```sh
flask attachments:install
flask db:migrate
```

The install command preserves existing storage configuration and does not create
duplicate migrations. Models, resources, and scaffolds accept `avatar:attachment`
and `documents:attachments`. See [Attachments](attachments.md).

## Tests

Run model, integration, job, and mailer tests with `flask test`. Run browser tests with `flask test:system`. Both commands accept pytest arguments. See [Testing](../testing.md) for setup and examples.
