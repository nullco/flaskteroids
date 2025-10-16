<p align="center">
  <a href="https://github.com/nullco/flaskteroids">
    <img src="https://raw.githubusercontent.com/nullco/flaskteroids/main/docs/images/logo.png" alt="Flaskteroids Logo" width="200">
  </a>
</p>

<h1 align="center">Flaskteroids</h1>

<p align="center">
  <strong>Flask on Steroids: A Python MVC framework inspired by Ruby on Rails.</strong>
</p>

<p align="center">
  <a href="https://github.com/nullco/flaskteroids/actions/workflows/test.yml?query=branch%3Amain++" target="_blank">
    <img src="https://github.com/nullco/flaskteroids/actions/workflows/test.yml/badge.svg?event=push&branch=main" alt="Build Status">
  </a>
  <a href="https://pypi.org/project/flaskteroids/" target="_blank">
    <img src="https://img.shields.io/pypi/v/flaskteroids.svg" alt="PyPI Version">
  </a>
  <a href="https://pypi.org/project/flaskteroids/" target="_blank">
    <img src="https://img.shields.io/pypi/pyversions/flaskteroids.svg" alt="Python Versions">
  </a>
  <a href="https://github.com/nullco/flaskteroids/blob/main/LICENSE" target="_blank">
    <img src="https://img.shields.io/github/license/nullco/flaskteroids.svg" alt="License">
  </a>
</p>

---

**Flaskteroids** is a lightweight and powerful Python MVC framework that enhances Flask with a structured and elegant abstraction. Inspired by the APIs of Ruby on Rails, it simplifies web application development while leveraging the robustness of Flask.

It brings the proven philosophy of **convention over configuration** to Python, allowing you to build scalable and maintainable applications with speed and confidence.

## Features

- **Full MVC Architecture**: Clean separation of concerns with Models, Views, and Controllers.
- **Elegant Routing**: Intuitive and resourceful routing inspired by Rails.
- **Built-in ORM**: Seamless integration with SQLAlchemy and Alembic for database management and migrations.
- **Powerful CLI**: A rich set of commands for generating models, controllers, mailers, scaffolds, and more.
- **Background Jobs**: Integrated with Celery for easy background job processing.
- **RESTful by Design**: Quickly build API routes with JSON responses.
- **Flask Compatibility**: Retains the full power of Flask and its rich ecosystem.

## Table of Contents

- [Installation](#installation)
- [Getting Started](#getting-started)
  - [Creating a New App](#1-creating-a-new-app)
  - [Running the Server](#2-running-the-server)
- [Your First Feature: A Blog](#your-first-feature-a-blog)
- [Core Concepts](#core-concepts)
  - [Project Structure](#project-structure)
  - [Routing](#routing)
  - [Controllers](#controllers)
  - [Models](#models)
- [Command-Line Interface (CLI)](#command-line-interface-cli)
  - [Generators](#generators)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

## Installation

To get started, install the Flaskteroids package using `pip`:

```sh
pip install flaskteroids
```

## Getting Started

### 1. Creating a New App

Create a new Flaskteroids application using the `flaskteroids new` command:

```sh
flaskteroids new my_project
cd my_project
```

This creates a new directory called `my_project` with a standard application structure.

### 2. Running the Server

To start the development server, run:

```sh
flask run
```

Now, open your browser and navigate to `http://127.0.0.1:5000`. You should see the Flaskteroids welcome page!

## Your First Feature: A Blog

Let's create a simple blog to see the power of scaffolding.

1.  **Generate a Post scaffold:**
    This command will create the model, controller, views, and database migration for a `Post` resource with `title` and `content` fields.

    ```sh
    flask generate scaffold Post title:string content:text
    ```

2.  **Run the database migration:**
    Apply the changes to your database schema.

    ```sh
    flask db:migrate
    ```

3.  **Start the server:**

    ```sh
    flask run
    ```

Now, visit `http://1227.0.0.1:5000/posts` in your browser. You have a complete set of pages to create, view, update, and delete posts.

## Core Concepts

### Project Structure

A typical Flaskteroids project follows this structure:

```
my_project/
├── app/
│   ├── controllers/
│   ├── models/
│   ├── mailers/
│   └── views/
├── config/
│   └── routes.py
└── run.py
```

- `app/controllers`: Handle web requests and respond with data or rendered views.
- `app/models`: Define your application's data structure and database interactions.
- `app/views`: Contain the templates for your application's UI.
- `config/routes.py`: Define the URL routes for your application.

### Routing

Routes are defined in `config/routes.py` by a `register` function that receives a router instance. You can define standard routes or use resourceful routing to handle RESTful conventions automatically.

```python
# config/routes.py
def register(router):
    # A standard route
    router.get("/", to="welcome#index")

    # Resourceful routes for a 'posts' controller
    router.resources("posts")
```

### Controllers

Controllers handle the logic for incoming requests. Actions are methods within a controller class that set instance variables for the view. Rendering is handled automatically.

```python
# app/controllers/posts_controller.py
from flaskteroids.actions import params
from flaskteroids.controller import ActionController
from app.models.post import Post

class PostsController(ActionController):
    def index(self):
        self.posts = Post.all()
        # Implicitly renders app/views/posts/index.html and
        # makes @posts available in the template.

    def show(self):
        self.post = Post.find(params["id"])
        # Implicitly renders app/views/posts/show.html and
        # makes @post available in the template.
```

### Models

Models inherit from `flaskteroids.model.Model` and act as a rich wrapper around your database tables. Database columns are defined during migration and are automatically available as attributes on the model.

The `Model` class provides a powerful API for associations and data validation.

```python
# app/models/post.py
from flaskteroids.model import Model, validates, belongs_to, has_many

class Post(Model):
    # The database columns (e.g., title, content, user_id) are defined
    # in the database migration and automatically mapped to this model.

    # --- Associations ---
    belongs_to('user')
    has_many('comments')

    # --- Validations ---
    validates('title', presence=True, length={'minimum': 5})
    validates('content', presence=True)
```

## Command-Line Interface (CLI)

Flaskteroids extends the `flask` CLI with a powerful set of tools to streamline development.

### Generators

Use the `flask generate` command to create various components:

*   **Authentication:**
    ```sh
    flask generate authentication
    ```
    Sets up a complete authentication system (routes, controllers, views).

*   **Controller:**
    ```sh
    flask generate controller <controller_name> [action1 action2 ...]
    ```
    *Example:* `flask generate controller users index show`

*   **Mailer:**
    ```sh
    flask generate mailer <mailer_name> [action1 action2 ...]
    ```
    *Example:* `flask generate mailer UserMailer welcome_email`

*   **Migration:**
    ```sh
    flask generate migration <migration_name>
    ```

*   **Model:**
    ```sh
    flask generate model <model_name> [field1:type ...]
    ```
    *Example:* `flask generate model User name:string email:string`

*   **Resource:**
    ```sh
    flask generate resource <resource_name> [field1:type ...]
    ```
    Generates a model and a RESTful controller.

*   **Scaffold:**
    ```sh
    flask generate scaffold <scaffold_name> [field1:type ...]
    ```
    Generates a model, RESTful controller, and views.

## Testing

Flaskteroids is designed for testability. To run your application's test suite, use `pytest`:

```sh
pytest
```

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) to get started.

## License

Flaskteroids is open-source and released under the [MIT License](LICENSE).