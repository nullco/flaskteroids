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

It provides a "batteries-included" experience while being extremely selective about external dependencies, ensuring the core framework remains lean, fast, and secure.

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
    - [Controller Callbacks](#controller-callbacks)
    - [Content Negotiation](#content-negotiation)
  - [Models](#models)
  - [Views](#views)
  - [Mailers](#mailers)
  - [Background Jobs](#background-jobs)
  - [Flash Messaging](#flash-messaging)
  - [Handling Forms](#handling-forms)
    - [Building Forms](#building-forms)
    - [Strong Parameters](#strong-parameters)
    - [CSRF Protection](#csrf-protection)
- [Security](#security)
  - [Rate Limiting](#rate-limiting)
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

1.  **Create a new app:**
    This command will create a new Flaskteroids application in a directory called `my_blog`.

    ```sh
    flaskteroids new my_blog
    cd my_blog
    ```

2.  **Generate a Post scaffold:**
    This command will create the model, controller, views, and database migration for a `Post` resource with `title` and `content` fields.

    ```sh
    flask generate scaffold Post title:string content:text
    ```

3.  **Run the database migration:**
    Apply the changes to your database schema.

    ```sh
    flask db:migrate
    ```

4.  **Start the server:**

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
│   ├── views/
│   └── jobs/
├── config/
│   └── routes.py
└── run.py
```

- `app/controllers`: Handle web requests and respond with data or rendered views.
- `app/models`: Define your application's data structure and database interactions.
- `app/views`: Contain the templates for your application's UI.
- `app/mailers`: Handle sending emails.
- `app/jobs`: Define background jobs to be run asynchronously.
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
from flaskteroids import params
from flaskteroids.controller import ActionController
from app.controllers.application_controller import ApplicationController
from app.models.post import Post

class PostsController(ApplicationController):
    def index(self):
        self.posts = Post.all()
        # Implicitly renders app/views/posts/index.html and
        # makes @posts available in the template.

    def show(self):
        self.post = Post.find(params["id"])
        # Implicitly renders app/views/posts/show.html and
        # makes @post available in the template.
```

#### Controller Callbacks

You can use callbacks to run code before a controller action. The `before_action` callback is useful for setting up instance variables or performing authentication checks. Callbacks must be defined within a `@rules` decorator.

```python
from flaskteroids import params
from flaskteroids.actions import before_action
from flaskteroids.rules import rules
from app.controllers.application_controller import ApplicationController
from app.models.post import Post

@rules(
    before_action('_set_post', only=['show', 'edit', 'update', 'destroy'])
)
class PostsController(ActionController):
    def show(self):
        # self.post is already set by the callback
        pass

    def _set_post(self):
        self.post = Post.find(params["id"])
```

#### Content Negotiation

Flaskteroids can handle different response formats within a single action using the `respond_to` block. This is particularly useful for building APIs that serve both HTML and JSON.

```python
from flaskteroids.controller import respond_to
from app.controllers.application_controller import ApplicationController
from app.models.post import Post

class PostsController(ActionController):
    def index(self):
        self.posts = Post.all()
        with respond_to() as format:
            format.html(lambda: render('index'))
            format.json(lambda: render(json=self.posts))
```

### Models

Models inherit from `flaskteroids.model.Model` and act as a rich wrapper around your database tables. Database columns are defined during migration and are automatically available as attributes on the model.

The `Model` class provides a powerful API for associations and data validation.

```python
# app/models/post.py
from flaskteroids.model import Model, validates, belongs_to, has_many
from flaskteroids.rules import rules

@rules(
    # --- Associations ---
    belongs_to('user'),
    has_many('comments'),

    # --- Validations ---
    validates('title', presence=True, length={'minimum': 5}),
    validates('content', presence=True)
)
class Post(Model):
    # The database columns (e.g., title, content, user_id) are defined
    # in the database migration and automatically mapped to this model.
    pass
```

### Views

Views are the user-facing part of your application. Flaskteroids uses Jinja2 for templating, which is the default for Flask. Templates are located in the `app/views` directory and are automatically rendered by controller actions.

Instance variables set in the controller are available in the corresponding view file.

```html
<!-- app/views/posts/index.html -->
{% extends "layouts/application.html" %}

{% block body %}
<h1>Posts</h1>

<ul>
  {% for post in posts %}
  <li>{{ post.title }}</li>
  {% endfor %}
</ul>
{% endblock %}
```

### Mailers

Mailers inherit from `ActionMailer` and are used to send emails from your application. They work similarly to controllers, with actions that correspond to email templates.

```python
# app/mailers/user_mailer.py
from flaskteroids.mailer import ActionMailer

class UserMailer(ActionMailer):
    def welcome_email(self, user):
        self.user = user
        self.mail(to=user.email, subject="Welcome to My App!")
```

You can then deliver the email synchronously or asynchronously:

```python
# Deliver now
UserMailer().welcome_email(user).deliver_now()

# Deliver later using a background job
UserMailer().welcome_email(user).deliver_later()
```

### Background Jobs

For long-running tasks, you can use background jobs. Jobs inherit from `Job` and define a `perform` method.

```python
# app/jobs/my_job.py
from flaskteroids.jobs.job import Job

class MyJob(Job):
    def perform(self, user_id):
        # Do some long-running task
        print(f"Performing job for user {user_id}")
```

To enqueue a job, call `perform_later`:

```python
MyJob().perform_later(user_id=1)
```

### Flash Messaging

Flaskteroids provides a `flash` object for setting and displaying temporary messages.

In your controller, you can set a message like this:

```python
from flaskteroids.flash import flash

class PostsController(ActionController):
    def create(self):
        # ... create post
        flash['notice'] = "Post was successfully created."
        # redirect
```

Then, in your view, you can display the message:

```html
{% if flash.notice %}
  <div class="notice">{{ flash.notice }}</div>
{% endif %}
```

### Handling Forms

Handling user input from forms is a common task in web applications. Flaskteroids provides a cohesive set of tools to build forms, handle submissions securely, and prevent common vulnerabilities.

#### Building Forms

Flaskteroids provides a simple and powerful way to build forms using the `form_with` helper and the `Form` object. The `form_with` helper can be used with a model object to automatically generate the form's action and method, and it also includes the CSRF token automatically.

Here's an example of how to create a form for a `Post` model:

```html
<!-- app/views/posts/_form.html -->
{% call(form) form_with(model=post) %}
  <div>
    {{ form.label('title') }}
    {{ form.text_field('title') }}
  </div>

  <div>
    {{ form.label('content') }}
    {{ form.text_area('content') }}
  </div>

  <div>
    {{ form.submit('Save') }}
  </div>
{% endcall %}
```

The `form` object provides a variety of helpers for generating form fields, such as `text_field`, `text_area`, `password_field`, `checkbox`, and more.

#### Strong Parameters

To prevent mass assignment vulnerabilities, Flaskteroids uses a technique inspired by Rails' **Strong Parameters**. The `params` object allows you to whitelist which parameters are permitted in your controller actions.

This is a security best practice that ensures users cannot update model attributes they are not supposed to, such as an admin flag.

Here's how you can use `params.expect` to safely handle incoming data. The `expect` method allows you to define the structure of the expected parameters, including nested objects and lists.

```python
# app/controllers/posts_controller.py
from flaskteroids import params
from flaskteroids.controller import ActionController
from app.models.post import Post

class PostsController(ActionController):
    # ...

    def create(self):
        self.post = Post.new(_post_params())
        if self.post.save():
            # ... success
        else:
            # ... error
            pass

    def update(self):
        self.post = Post.find(params['id'])
        if self.post.update(_post_params()):
            # ... success
        else:
            # ... error
            pass

    def _post_params(self):
        # Assumes form data is sent as:
        # post[title]=...
        # post[content]=...
        return params.expect(post=['title', 'content'])

```

In this example, `_post_params` specifies that the `params` object must contain a top-level key called `post`, which should be a dictionary containing only the `title` and `content` keys. Any other attributes within the `post` object will be discarded, and if the `post` key is missing or the structure is incorrect, an exception will be raised.

#### CSRF Protection

Flaskteroids automatically includes CSRF (Cross-Site Request Forgery) protection on all non-GET requests. A CSRF token is generated and must be included in your forms. The `form_with` helper does this automatically.

For manual forms, you can include the token like this:

```html
<form action="/posts" method="post">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <!-- ... form fields -->
</form>
```

## Security

### Rate Limiting

You can easily add rate limiting to your controllers to prevent abuse. The `rate_limit` decorator allows you to specify the maximum number of requests allowed within a given time window.

```python
from flaskteroids.rate_limit import rate_limit

@rate_limit(to=10, within=60) # 10 requests per 60 seconds
class PostsController(ActionController):
    # ...
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