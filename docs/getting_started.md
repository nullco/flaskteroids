# Getting started

## Installation

Requires Python 3.12 or newer. Install Flaskteroids in your Python environment:

```sh
pip install flaskteroids
```

## Create an application

Git must be installed. Run:

```sh
flaskteroids new my_app
cd my_app
```

The command creates the application files and initializes a Git repository in `my_app`. It does not install dependencies. See [Project structure](project_structure.md) for the generated directory layout.

## Run the server

```sh
flask run
```

Open `http://127.0.0.1:5000` to see the welcome page.

Flaskteroids uses the `development` environment by default. Set `FLASK_ENV` to select another environment:

```sh
FLASK_ENV=test flask run
```

The generated application stores its secrets in encrypted credentials. Edit or inspect them with:

```sh
flask credentials:edit
flask credentials:show
```

See [Configuration](configuration.md) for environments, credentials, and the boot process.

## Add a posts resource

Stop the server and generate a `Post` scaffold inside `my_app`:

```sh
flask generate scaffold Post title:string content:text
```

This creates a model, database migration, controller, views, and routes for posts with `title` and `content` fields.

Apply the migration and restart the server:

```sh
flask db:migrate
flask run
```

Visit `http://127.0.0.1:5000/posts/` to create, view, edit, and delete posts.

## Next steps

Read the [models](models/index.md), [views](views/index.md), and [controllers](controllers/index.md) guides to change the generated code. See [Testing](testing.md) to run the application's tests.
