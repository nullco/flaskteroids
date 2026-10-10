# Command-line interface

Flaskteroids extends the `flask` CLI with generators, database tasks, credentials commands, and test runners. Run application commands from the application root. Use `flask --help` to list commands and `flask <command> --help` for usage.

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

## Tests

Run model, integration, job, and mailer tests with `flask test`. Run browser tests with `flask test:system`. Both commands accept pytest arguments. See [Testing](../testing.md) for setup and examples.
