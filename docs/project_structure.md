# Project structure

Most application work happens in three places: `app/` for behavior and templates,
`config/` for settings and routes, and `db/` for database changes.
`flask new` creates the layout below.

After reading this guide, you will know how to:

- Find the files used by models, controllers, and views.
- Recognize generated files and files you should commit.
- Set up an existing application checkout.

## Directory layout

```text
my_project/
├── app/
│   ├── assets/
│   ├── controllers/
│   ├── helpers/
│   ├── javascript/application.js
│   ├── models/
│   ├── mailers/
│   ├── views/
│   └── jobs/
├── bin/                 # flask, importmap, jobs, setup, release, docker-entrypoint
├── deploy/README.md
├── Dockerfile
├── .dockerignore
├── config/
│   ├── environments/
│   │   ├── development.py
│   │   ├── test.py
│   │   └── production.py
│   ├── locales/en.yml   # application translations
│   ├── initializers/
│   ├── importmap.py      # browser module pins
│   ├── application.py
│   ├── boot.py
│   ├── credentials.yml.enc
│   ├── database.yml
│   ├── environment.py
│   └── routes.py
├── db/
│   ├── schema.py        # generated database snapshot; commit, do not edit
│   └── migrate/
├── public/assets/       # fingerprinted build output and manifest; not committed
├── storage/
├── vendor/javascript/   # downloaded modules; commit these
├── test/
├── pyproject.toml
├── uv.lock              # created by installation; commit this
├── jobs.py
├── Procfile
└── wsgi.py
```

## Where to make changes

| Path | Contents |
| --- | --- |
| `app/assets` | Source stylesheets/images, served automatically in development/test. |
| `app/javascript` | Application JavaScript modules and entrypoints. |
| `vendor/javascript` | Downloaded, versioned JavaScript modules. |
| `config/importmap.py` | Logical JavaScript module mappings. |
| `bin/importmap` | Resolve, pin, and maintain downloaded JavaScript modules. |
| `public/assets` | Fingerprinted production assets and manifest, created by precompilation. |
| `app/controllers` | Request-handling actions. |
| `app/helpers` | Automatically loaded presentation helper classes. |
| `app/models` | Data rules and behavior: associations, validations, and callbacks. |
| `db/schema.py` | Generated column/table definitions. Commit this file; change the database through migrations, not by editing it. |
| `app/views` | Jinja templates. |
| `app/mailers` | Email actions. |
| `app/jobs` | Background jobs. |
| `config/application.py` | Application-wide configuration. |
| `config/environments` | Environment-specific overrides. |
| `config/initializers` | Library configuration that runs during boot. |
| `config/database.yml` | Database connections by environment. |
| `config/credentials.yml.enc` | Encrypted application secrets. |
| `config/routes.py` | Application routes. |
| `config/locales` | YAML translation catalogs. |
| `db/migrate` | Database migrations. |
| `storage` | Local database files and uploads; keep persistent in containers. |
| `bin/flask` | Run Flask commands using your app's environment. |
| `bin/jobs start` | Start a background job worker using your app's environment. |
| `bin/setup` | Install dependencies and prepare the database. |
| `bin/release migrate` | Apply database changes during deployment. |
| `bin/docker-entrypoint` | Start the Docker application. |
| `uv.lock` | Exact dependency versions; commit this file. |
| `deploy/README.md` | Your app's Docker and deployment guide. |
| `Procfile` | Example web and worker process commands. |
| `test` | Tests and YAML fixtures. |

## Set up an existing checkout

A new app is ready to run. When you check out an existing project—or create one
with `--skip-install`—run `bin/setup` to install its dependencies and prepare the
database:

```sh
bin/setup
```

Next, explore [Configuration](configuration.md) to choose settings for each
environment, or [Assets](other/assets.md) to add styles and images.
