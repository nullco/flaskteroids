# Getting Started

**Flaskteroids** (or Flask on Steroids) is a lightweight yet powerful Python MVC framework designed to provide the closest possible experience to developing web applications in **Ruby on Rails**, but with the power and flexibility of Python. By supercharging **Flask** with Rails-inspired conventions and structure, Flaskteroids enables developers to build full-featured web applications with unprecedented speed and elegance.

Our mission is to bring the proven productivity and developer happiness of Rails to the Python ecosystem, offering a batteries-included framework that emphasizes **convention over configuration**. This means you can focus on building great applications rather than boilerplate code, while maintaining the full power of Flask and its rich ecosystem.

Flaskteroids stays lean, fast, and secure by carefully selecting core dependencies and providing everything you need out of the box — from database management to background jobs — without unnecessary complexity.

## Features

- **Full MVC Architecture**: Clean separation of concerns with Models, Views, and Controllers, just like Rails.
- **Elegant Routing**: Intuitive and resourceful routing that automatically generates RESTful routes for your resources.
- **Built-in ORM**: Seamless integration with SQLAlchemy and Alembic for database management and migrations.
- **Background Jobs**: Integrated with Celery for easy background job processing.
- **RESTful by Design**: Quickly build API routes with automatic JSON responses for data-oriented actions.
- **Powerful CLI**: A rich set of commands for generating models, controllers, mailers, scaffolds, and more — inspired by Rails generators.
- **Flask Compatibility**: Retains the full power of Flask and its rich ecosystem while adding Rails-like productivity.
- **Convention Over Configuration**: Sensible defaults and automatic discovery reduce boilerplate code.

## Installation

```sh
pip install flaskteroids
```

## Creating a New App

Create a new Flaskteroids application using the `flaskteroids new` command:

```sh
flaskteroids new my_app
cd my_app
```

This creates a new directory called `my_app` with a standard Rails-inspired application structure.

## Project Structure

A typical Flaskteroids application follows this structure:

```
my_app/
├── app/
│   ├── controllers/     # Controllers handle requests and responses
│   ├── models/          # Models represent database tables and business logic
│   ├── views/           # Templates for rendering HTML
│   └── mailers/         # Email templates and logic
├── config/
│   ├── routes.py        # Route definitions
├── db/
│   └── migrations/      # Database migration files
├── public/              # Static assets (CSS, JS, images)
├── tests/               # Test files
├── pyproject.toml       # Project configuration
└── wsgi.py               # Main application entry point
```

## Running the Server

To start the development server, run:

```sh
flask run
```

Now, open your browser and navigate to `http://127.0.0.1:5000`.
You should see the Flaskteroids welcome page!

## Your First Feature: A Blog

Let's create a simple blog to see the power of scaffolding.
Inside your `my_app` follow the next steps:

1. **Generate a Post scaffold:**
   This command will create the model, controller, views, and database
   migration for a `Post` resource with `title` and `content` fields.

   ```sh
   flask generate scaffold Post title:string content:text
   ```

2. **Run the database migration:**
   Apply the changes to your database schema.

   ```sh
   flask db:migrate
   ```

3. **Start the server:**

   ```sh
   flask run
   ```

Now, visit `http://127.0.0.1:5000/posts` in your browser.
You have a complete set of pages to create, view, update, and delete posts.

## Next Steps

Congratulations on creating your first Flaskteroids application! Here are some suggestions for what to explore next:

- **Learn the Basics**: Dive deeper into [Models](models.md), [Views](views.md), [Controllers](controllers.md), and [Routing](routing.md).
- **Add Authentication**: Use the secure password features to add user authentication.
- **Background Jobs**: Explore Celery integration for handling asynchronous tasks.
