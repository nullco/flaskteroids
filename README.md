<!--<p align="center">
  <a href="https://github.com/nullco/flaskteroids">
    <img src="https://raw.githubusercontent.com/nullco/flaskteroids/main/docs/images/logo.png" alt="Flaskteroids Logo" width="200">
  </a>
</p>-->

<h1 align="center">Flaskteroids</h1>

<p align="center">
  <strong>Flaskteroids: A complete, batteries-included Python MVC framework inspired by Ruby on Rails.</strong>
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

**Flaskteroids** (or Flask on Steroids) is a lightweight yet powerful
Python MVC framework that supercharges **Flask** with a clean, elegant structure.
Inspired by the best of **Ruby on Rails**, it brings clarity and productivity
to your web development workflow.

Built on the philosophy of **convention over configuration**, Flaskteroids helps
you move fast, write less code, and stay focused on what matters: building
scalable, maintainable applications with confidence.

With a **batteries-included** approach and carefully chosen core dependencies,
Flaskteroids stays lean, fast, and secure — giving you everything you need,
and nothing you don’t.

## Features

- **Full MVC Architecture**: Clean separation of concerns with Models, Views,
  and Controllers.
- **Elegant Routing**: Intuitive and resourceful routing.
- **Built-in ORM**: Seamless integration with SQLAlchemy and Alembic for database management and migrations.
- **Background Jobs**: Integrated with Celery for easy background job processing.
- **RESTful by Design**: Quickly build API routes with JSON responses.
- **Powerful CLI**: A rich set of commands for generating models, controllers, mailers, scaffolds, and more.
- **Flask Compatibility**: Retains the full power of Flask and its rich ecosystem.

## Table of Contents

- [Installation](#installation)
- [Getting Started](#getting-started)
  - [Creating a New App](#1-creating-a-new-app)
  - [Running the Server](#2-running-the-server)
  - [Your First Feature: A Blog](#your-first-feature-a-blog)
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
flaskteroids new my_app
cd my_app
```

This creates a new directory called `my_app` with a standard application structure.

### 2. Running the Server

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

Now, visit `http://1227.0.0.1:5000/posts` in your browser.
You have a complete set of pages to create, view, update, and delete posts.

For more check out the [documentation](https://nullco.github.io/flaskteroids/index.html)

## License

Flaskteroids is open-source and released under the [MIT License](LICENSE).
