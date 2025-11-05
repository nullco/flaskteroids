# Command-Line Interface (CLI)

Flaskteroids extends the `flask` CLI with a powerful set of tools to streamline development.

## Generators

Use the `flask generate` command to create various components:

### Migration

Allows generation of database migrations. You can specify different migration commands
depending on what you want to achieve. All tables come by default with an auto-increment
`id` field, and a `created_at` date field.

#### Creating new tables

```sh
flask generate migration <CreateXXXTable> [field1:type ...]
```

*Example:* `flask generate migration CreateProducts name:string!`

#### Adding columns to existing table

```sh
flask generate migration <AddXXXToXXX> [field1:type ...]
```

*Example:* `flask generate migration AddPriceToProducts price:float`

#### Removing columns from an existing table

```sh
flask generate migration <RemoveXXXFromXXX> [field1 ...]
```

*Example:* `flask generate migration RemovePriceFromProducts price`

#### Dropping an existing table

```sh
flask generate migration <DropXXXX> [field1 ...]
```

*Example:* `flask generate migration DropProducts`

### Model

This will created together a Model and it's corresponding migration.
See [Migrations](#migration) for further details.

```sh
flask generate model <ModelName> [field1:type ...]
```

*Example:* `flask generate model User name:string email:string`

### Controller

This will generate:

* A new controller with the actions specified.
* A views for each action.
* Entries in routes file linking all controller actions individually

```sh
flask generate controller <ControllerName> [action1 action2 ...]
```

*Example:* `flask generate controller Users index show`

### Resource

This will Generate:

* A model and it's migration.
* An empty controller associated to that model.
* A resource entry linking the controller in routes.

All the code is up to be written by you.

```sh
flask generate resource <ResourceName> [field1:type ...]
```

Generates a model and a RESTful controller.

### Scaffold

This will generate:

* A model and it's migration.
* A controller associated to that model fully supporting CRUD operations.
  (The controller will have `index`, `show`, `new`, `edit`, `create`, `update`
  and `destroy` actions)
* All views backing up CRUD operations
* A resource entry linking the controller in routes.

```sh
flask generate scaffold <scaffold_name> [field1:type ...]
```

Generates a model, RESTful controller, and views.

### Mailer

```sh
flask generate mailer <MailerName> [action1 action2 ...]
```

*Example:* `flask generate mailer UserMailer welcome_email`

### Authentication

```sh
flask generate authentication
```

Sets up a complete authentication system
(routes, controllers, views and models for managing users and sessions).

It will add:

* A `User` model (email, password_digest).
* A `Session` model (user_id, ip_address, user_agent).
* Views and Controllers for logging in.
* Views and Controllers for editing passwords
* Views and Mailers for resetting user passwords
* Routes for session and password management
