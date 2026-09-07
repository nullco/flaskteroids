# Project Structure

A Flaskteroids project uses the following application structure:

```text
my_project/
├── app/
│   ├── controllers/
│   ├── models/
│   ├── mailers/
│   ├── views/
│   └── jobs/
├── config/
│   ├── environments/
│   │   ├── development.py
│   │   ├── test.py
│   │   └── production.py
│   ├── initializers/
│   ├── application.py
│   ├── boot.py
│   ├── credentials.yml.enc
│   ├── database.yml
│   ├── environment.py
│   └── routes.py
├── db/
│   └── migrate/
├── storage/
├── tests/
├── pyproject.toml
└── wsgi.py
```

- `app/controllers`: Handle web requests and responses.
- `app/models`: Define database-backed models and business logic.
- `app/views`: Contain Jinja templates.
- `app/mailers`: Define mail delivery actions.
- `app/jobs`: Define background jobs.
- `config/application.py`: Holds application-wide configuration.
- `config/environments`: Holds environment-specific overrides.
- `config/initializers`: Configures external libraries during boot.
- `config/database.yml`: Defines database connections by environment.
- `config/credentials.yml.enc`: Stores encrypted application secrets.
- `config/routes.py`: Defines application routes.
- `db/migrate`: Contains database migrations.

See [Configuration](configuration.md) for the boot process, environments, credentials, and database precedence.
