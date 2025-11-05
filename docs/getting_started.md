# Getting started

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

- **Learn the Basics**: Dive deeper into [Models](models/index.md), [Views](views/index.md) and [Controllers](controllers/index.md).
