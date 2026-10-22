# Command-line interface

Run commands from your project directory with `bin/flask`—no environment
activation needed. Use `bin/flask --help` to explore, or add `--help` to any command.
You can also use `flask` in an activated environment, or `uv run flask`.

## Generation and setup

```sh
flaskteroids new my_app
cd my_app
bin/flask run
bin/flask test
bin/flask test:system
```

Your new app comes with its dependencies installed and development database ready.
For a fresh checkout, run `bin/setup` before starting work.

Want to create the files first and install later? Use `--skip-install`, then run
`bin/setup` when you're ready. Commit `uv.lock` so your team shares the same
dependency versions.

## Asset precompilation

```sh
bin/flask assets:precompile
flaskteroids assets:precompile --root /path/to/app
```

Build assets for production. See [Assets](assets.md) for the full workflow.

## Database preparation

As your models grow, migrations describe how their tables should change. Run
`db:prepare` to create the database if needed and apply those migrations:

```sh
bin/flask db:prepare
```

To prepare another environment, choose it with `FLASK_ENV`:

```sh
FLASK_ENV=test bin/flask db:prepare
FLASK_ENV=production bin/flask db:prepare
```

Preparation doesn't reset the database or seed records. After successful migration,
Flaskteroids regenerates `db/schema.py` from the selected database. Commit this
read-only snapshot; do not duplicate column changes there by hand. Review migrations
and the resulting snapshot before deploying: changes and rollbacks can delete data.
Restart servers/workers afterward; published mappings are not modified in place.

| Command | When to use it |
| --- | --- |
| `db:prepare` | Get a database ready, or bring it up to date. |
| `db:create` | Create the database without applying migrations. |
| `db:migrate` | Apply pending migrations to an existing database. |
| `db:rollback` | Undo the most recent migration. |
| `db:init` | Add migration files to an app that doesn't have them yet. |
| `db:schema:dump` | Refresh `db/schema.py` from the selected database without changing data. |

New apps already include migration files. If preparation fails, fix the reported
problem and try again; the database is left in place for you to inspect. If migrations
succeed but snapshot publication fails, fix the file/access problem and run
`bin/flask db:schema:dump`; a failed file write does not undo applied migrations.

Commands use normal application initialization, including initializers. New model
declarations can be imported before their snapshot tables exist. An initializer
that actually constructs or queries an unavailable model still fails normally;
there is no migration-only startup mode.

For PostgreSQL or MySQL, start the server and
[configure its connection](../configuration.md#database-configuration) first.
For SQLite, use a database file rather than `:memory:` and make sure its parent
directory exists.

## Shell

`flask shell` provides your models and `session`:

```python
user = User.create(name="Alice")  # Commits before returning
with User.transaction():
    user.update(name="Alicia")
    User.create(name="Bob")
# Both changes commit at the end of the block.
```

Standalone `save()`, `create()`, `update()`, and `destroy()` commit immediately.
Use `Model.transaction()` to group changes; saves join that explicit transaction,
and an exception escaping the block rolls the group back. A `False` save result
does not itself abort an explicit block. Shell exit rolls back unfinished work;
it does not undo earlier standalone commits. Native writes require explicit
commit/transaction handling. Use `record.discard_changes()` or `record.reload()`
to discard staged input.

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

Generate a migration to create/drop a table or add/remove columns. New tables
include an auto-incrementing `id`, `created_at`, and `updated_at`. Standalone
migration generation does not edit the snapshot; applying the migration does.

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

Generate a behavioral model, its database migration, and tests. References add
`belongs_to(...)` declarations inside `@rules`. Columns appear in the generated
snapshot only after migration:

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

This also creates `app/helpers/users_helper.py` with a `UsersHelper` class.
Its public presentation methods are automatically available in templates; no
controller registration is needed. See [application helpers](../views/index.md#application-helpers).

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

- A `User` model with `email_address` and `password_digest`.
- A `Session` model with `user_id`, `ip_address`, and `user_agent`.
- Controllers and views for login and password changes.
- Views and mailers for password resets.
- Routes for session and password management.
- An `Authentication` concern added to `ApplicationController`, requiring login
  by default and exposing the `is_authenticated()` template helper.

Run `flask db:migrate`, then create an account in the shell; no public sign-up
form is generated. Use `skip_before_action("_require_authentication", only=[...])`
in a controller's `@rules` to allow public actions. Templates can call
`is_authenticated()` on both public and protected pages without an extra callback.
See [the authentication walkthrough](../getting_started.md#8-require-login-to-change-products).

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
