# Getting started

## Install and create

Requires Python 3.12+, Git, Bash, and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```sh
pip install flaskteroids
flaskteroids new my_app
cd my_app
source .venv/bin/activate
```

Generation installs dependencies and prepares your development database.

## Run and test

```sh
flask run
```

Open <http://127.0.0.1:5000>.

```sh
flask test
flask test:system
```

The app includes a health test. An empty system suite succeeds without a browser.

## Add posts

Stop the server, then generate a scaffold:

```sh
flask generate scaffold Post title:string content:text
flask db:prepare
flask run
```

Visit <http://127.0.0.1:5000/posts/> to create, view, edit, and delete posts.

The generator writes a behavioral model and a migration. `db:prepare` applies the
migration and generates `app/schema.py` from the database. Commit the snapshot;
make future schema changes through migrations, not by editing that file.

## Next steps

- Run `bin/setup` for a fresh checkout or after changing dependencies. Commit `uv.lock`.
- To defer installation, use `flaskteroids new my_app --skip-install`, then run `bin/setup` later.
- See [Testing](testing.md) for browser setup and [Configuration](configuration.md) for environments and secrets.
- Your generated `deploy/README.md` explains Docker and deployment.
