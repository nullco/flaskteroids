# Command-line interface

Run commands from your application directory with `bin/flask`; no environment
activation is needed. You can also use `flask` in an activated environment or
`uv run flask`.

Use `bin/flask --help` to list commands, or add `--help` to a specific command:

```sh
bin/flask generate --help
bin/flask db:migrate --help
```

## Generation and setup

```sh
flaskteroids new my_app
cd my_app
bin/flask run
```

A new app has its dependencies installed and development database prepared. For
a fresh checkout, run `bin/setup` first.

To generate files without installing, use `flaskteroids new my_app --skip-install`
and run `bin/setup` later. Commit `uv.lock` so the team shares dependency versions.

For an API instead of server-rendered pages, pass `--api` when creating the
application. Controller and scaffold generators then produce API output. See
[Building an API](../controllers/api.md) for a complete example.

## Database preparation

Migrations describe changes to database tables. To create a database if necessary
and apply pending migrations:

```sh
bin/flask db:prepare
```

Select another environment with `FLASKTEROIDS_ENV`:

```sh
FLASKTEROIDS_ENV=test bin/flask db:prepare
FLASKTEROIDS_ENV=production bin/flask db:prepare
```

Preparation does not reset the database or seed records.

| Command | When to use it |
| --- | --- |
| `db:prepare` | Create a database if needed and bring it up to date |
| `db:create` | Create a database without applying migrations |
| `db:migrate` | Apply pending migrations to an existing database |
| `db:rollback` | Undo the most recent migration |
| `db:init` | Add migration setup to an app that does not have it |
| `db:schema:dump` | Refresh `db/schema.py` without changing database data |

New applications already include migration setup.

### After a migration

Successful migrations regenerate `db/schema.py` from the selected database.
Commit this generated snapshot, but do not edit its columns by hand. Restart
servers and workers afterward so they load the new schema.

**Review migrations and rollbacks before running them in production:** either can
delete data. If a command fails, fix the reported problem and retry; the database
is left available for inspection. If migrations succeed but writing the snapshot
fails, fix the file/access problem and run `bin/flask db:schema:dump`. A failed
snapshot write does not undo database changes.

### Startup and connection requirements

Database commands use normal application startup, including initializers. New
models can be imported before their tables appear in the snapshot, but an
initializer that constructs or queries an unavailable model still fails. There
is no separate migration-only startup mode.

For PostgreSQL or MySQL, start the server and
[configure the connection](../configuration.md#database-configuration) first.
For SQLite, use a file rather than `:memory:` and ensure its parent directory
exists.

## Shell

Open an application-aware Python shell:

```sh
bin/flask shell
```

Your models and `session` are available:

```python
user = User.create(name="Alice")  # Commits before returning.
with User.transaction():
    user.update(name="Alicia")
    User.create(name="Bob")
# Both changes commit at the end of the block.
```

Standalone `save()`, `create()`, `update()`, and `destroy()` commit immediately.
Inside `Model.transaction()`, they join the block's transaction. An exception
escaping the block rolls the group back; a `False` save result does not.

Shell exit rolls back unfinished work, not earlier standalone commits. Native
SQLAlchemy writes need explicit commit/transaction handling. To discard pending
model input, use `record.discard_changes()` or `record.reload()`.
See [model transactions](../models/index.md#transactions).

## Credentials

```sh
bin/flask credentials:edit
bin/flask credentials:show
bin/flask credentials:edit --environment production
```

`edit` opens encrypted YAML for editing. `show` prints decrypted secrets: do not
copy its output into logs. Environment-specific credentials replace shared ones;
they do not merge with them. See
[encrypted credentials](../configuration.md#encrypted-credentials) for key setup.

## Generators

Use `bin/flask generate` to create application components. Fields use `name:type`,
such as `title:string`. See [Fields](fields.md) for supported types and modifiers.
The examples below use concrete names; replace them with your application's names.

### Migration

Generate a migration, review it, then apply it with `bin/flask db:migrate`.
Generating the file alone does not change the database or schema snapshot.

#### Create a table

```sh
bin/flask generate migration CreateProducts name:string!
```

Use the plural table name after `Create`, without a `Table` suffix. New tables
include an auto-incrementing `id`, `created_at`, and `updated_at`.

#### Add columns

```sh
bin/flask generate migration AddPriceToProducts price:float
```

#### Remove columns

```sh
bin/flask generate migration RemovePriceFromProducts price
```

#### Drop a table

```sh
bin/flask generate migration DropProducts
```

### Model

```sh
bin/flask generate model Post title:string author:references
```

Creates a model class, migration, and tests. References add `belongs_to(...)`
declarations. Columns become available in the schema snapshot after migration.

### Controller

```sh
bin/flask generate controller Users index show
```

Creates a controller with the named actions, a view for each, and individual
routes. It also creates `app/helpers/users_helper.py` with a `UsersHelper` class.
Its public methods are available in templates without controller registration.
See [application helpers](../views/index.md#application-helpers).

### Resource

```sh
bin/flask generate resource Product name:string price:float
```

Creates a model, migration, empty controller, and resource route. You write the
controller actions and views.

### Scaffold

```sh
bin/flask generate scaffold Product name:string price:float
```

Creates a model, migration, resource route, controller, and views for the standard
`index`, `show`, `new`, `edit`, `create`, `update`, and `destroy` actions. Apply the
migration and restart the server before visiting the resource.

New controller/scaffold page templates use `{% extends layout %}` for frame-aware
layout selection. Scaffold records use underscored `dom_id` values, and successful
updates redirect with 303. Scaffolds remain ordinary full-page CRUD, not inline
editors; see [Turbo Frames and Streams](../views/turbo.md) to add that behavior.

### Mailer

```sh
bin/flask generate mailer User welcome_email
```

Creates `UserMailer`, text and HTML templates, a test, and preview scenarios in
`test/mailers/previews/user_mailer_preview.py`. Supply the base name `User`, not
`UserMailer`. Browse examples at `/flaskteroids/mailers` in development. See
[Preview emails](mailers.md#preview-emails) for the walkthrough and
[Mailers](mailers.md#configure-delivery) for delivery configuration.

### Authentication

```sh
bin/flask generate authentication
bin/flask db:migrate
```

Creates a login and password-management workflow:

- `User` with `email_address` and `password_digest`.
- `Session` with `user_id`, `ip_address`, and `user_agent`.
- Controllers and views for login and password changes.
- Password-reset views and mailers.
- Routes for session and password management.
- An `Authentication` concern added to `ApplicationController`, requiring login
  by default and exposing the `is_authenticated()` template helper.

Create an account in the shell; no public sign-up form is generated. To allow a
public action, declare `skip_before_action("_require_authentication", only=[...])`
inside its controller class. Templates can call `is_authenticated()` on public
and protected pages without an extra callback. See
[the authentication walkthrough](../getting_started.md#8-require-login-to-change-products).

## Attribute encryption

```sh
bin/flask db:encryption:init
bin/flask credentials:edit
```

The first command prints dedicated primary and deterministic keys. Copy its
`encryption` YAML into the credentials editor; it does not save keys itself.
Do not commit or log the plaintext output.

These keys serve model `encrypts(...)`, encrypted rich text, and direct use of
`flaskteroids.encryption`. See [Attribute encryption](../models/encryption.md).

## Turbo

```sh
bin/flask turbo:install
```

Configures the framework-provided Turbo 8.0.23 ESM asset through import maps,
preserving application code. Layouts without script tags receive the module
helper; customized script layouts receive instructions instead. Existing views are not rewritten and no
runtime is copied or downloaded. New applications already include this setup.
See [Turbo installation](../views/turbo.md#install-or-upgrade).

## Import maps

```sh
bin/flask importmap:install
bin/importmap pin @github/hotkey
bin/importmap pin @github/hotkey@3.1.1 --no-preload
bin/importmap packages
bin/importmap update
bin/importmap pristine
bin/importmap unpin @github/hotkey
bin/importmap json --environment production
```

The installer creates `config/importmap.py`, `app/javascript/application.js`, and
`bin/importmap` without replacing application code. Package commands resolve
through JSPM and vendor returned modules, without booting the application.
Use `flaskteroids importmap --root /path/to/app COMMAND` outside the application.
See [Import maps](importmaps.md) for configuration, options, and package limits.

## Rich text

```sh
bin/flask rich_text:install
bin/flask db:migrate
```

Configures import-map pins and the entrypoint for the framework-provided Lexxy
editor, adds its stylesheet helper to the layout, and creates rich-text and
attachment migrations as needed. It does not copy runtime assets. Repeated runs
preserve application code and avoid duplicate migrations.

Upgrading the locked Flaskteroids dependency upgrades the supplied editor;
precompile production assets and restart. Model, resource, and scaffold
generators accept `content:rich_text`. See [Rich text](rich_text.md).

## Attachments

```sh
bin/flask attachments:install
bin/flask db:migrate
```

Creates attachment migrations and storage configuration without replacing
existing configuration or duplicating migrations. Generators accept
`avatar:attachment` for one file and `documents:attachments` for several.
See [Attachments](attachments.md).

## Asset precompilation

```sh
bin/flask assets:precompile
flaskteroids assets:precompile --root /path/to/app
```

Builds fingerprinted assets for production. Both commands work without application
startup or database access. Generated Docker builds already precompile assets.
See [Assets](assets.md).

## Tests

```sh
bin/flask test
bin/flask test:system
bin/flask test test/models/post_test.py
```

`test` runs model, integration, job, and mailer tests. `test:system` runs browser
tests. Both accept pytest arguments. See [Testing](../testing.md) for fixtures,
assertions, and browser installation.
