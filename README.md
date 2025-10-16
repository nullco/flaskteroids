<p align="center">
<a href="https://github.com/nullco/flaskteroids/actions/workflows/test.yml?query=branch%3Amain++" target="_blank">
    <img src="https://github.com/nullco/flaskteroids/actions/workflows/test.yml/badge.svg?event=push&branch=main" alt="Test">
</a>
</p>

# Flaskteroids

Flaskteroids (or Flask on steroids) is a lightweight and powerful Python MVC framework that enhances Flask with a structured and elegant abstraction. Inspired by the APIs of Ruby on Rails, it simplifies web application development while leveraging the robustness of Flask.

## Features

- **MVC Architecture** – A clean separation of concerns using Models, Views, and Controllers.
- **Elegant Routing** – Inspired by Rails for intuitive route definition.
- **Built-in ORM Support** – Seamlessly integrates with SQLAlchemy for database management and Alembic for migrations.
- **Powerful CLI Tooling** – Simplifies project management with command-line utilities for generating models, controllers, mailers, scaffolds, and more.
- **Templating Engine** – Works effortlessly with Jinja2 for dynamic views.
- **RESTful API Support** – Easy-to-define API routes with JSON responses.
- **Background Jobs** – Integrated with Celery for background job execution.
- **Flask Compatibility** – Retains the full power of Flask and its ecosystem.

## Installation

```sh
pip install flaskteroids
```

## Getting Started

To create a new Flaskteroids application, use the `flaskteroids new` command:

```sh
flaskteroids new my_project
```

This will create a new directory called `my_project` with the basic application structure.

## Project Structure

A typical Flaskteroids project follows this structure:

```sh
my_project/
├── app/
│   ├── controllers/
│   │   └── welcome_controller.py
│   ├── models/
│   ├── mailers/
│   └── views/
│       └── welcome/
│           └── index.html
├── config/
│   └── routes.py
└── run.py
```

## Command-Line Interface (CLI)

Flaskteroids extends the `flask` command-line interface with a powerful set of tools to streamline development.

### Generators

You can use the `flask generate` command to create various components of your application:

*   **Authentication:**
    ```sh
    flask generate authentication
    ```
    This command sets up a complete authentication system, including routes, controllers, and views for user authentication.

*   **Controller:**
    ```sh
    flask generate controller <controller_name> [action1 action2 ...]
    ```
    This command creates a new controller with the specified actions. For example:
    ```sh
    flask generate controller users index show
    ```

*   **Mailer:**
    ```sh
    flask generate mailer <mailer_name> [action1 action2 ...]
    ```
    This command generates a new mailer class with the specified actions. For example:
    ```sh
    flask generate mailer UserMailer welcome_email
    ```

*   **Migration:**
    ```sh
    flask generate migration <migration_name>
    ```
    This command creates a new database migration file.

*   **Model:**
    ```sh
    flask generate model <model_name> [field1:type field2:type ...]
    ```
    This command creates a new model with the specified attributes. For example:
    ```sh
    flask generate model User name:string email:string
    ```

*   **Resource:**
    ```sh
    flask generate resource <resource_name> [field1:type field2:type ...]
    ```
    This command generates a model and a controller with the standard set of RESTful actions (index, show, new, create, edit, update, destroy).

*   **Scaffold:**
    ```sh
    flask generate scaffold <scaffold_name> [field1:type field2:type ...]
    ```
    This command generates a model, a controller with RESTful actions, and the corresponding views for a complete resource.

## License

Flaskteroids is open-source and released under the MIT License.
