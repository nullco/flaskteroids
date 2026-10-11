# Project structure

`flaskteroids new` generates this application layout. The tree shows the main directories and configuration files:

```text
my_project/
├── app/
│   ├── assets/
│   ├── controllers/
│   ├── helpers/
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
├── test/
├── pyproject.toml
└── wsgi.py
```

| Path | Contents |
| --- | --- |
| `app/assets` | Stylesheets and images. |
| `app/controllers` | Request-handling actions. |
| `app/helpers` | Template helpers. |
| `app/models` | Database-backed models and business logic. |
| `app/views` | Jinja templates. |
| `app/mailers` | Email actions. |
| `app/jobs` | Background jobs. |
| `config/application.py` | Application-wide configuration. |
| `config/environments` | Environment-specific overrides. |
| `config/initializers` | Library configuration that runs during boot. |
| `config/database.yml` | Database connections by environment. |
| `config/credentials.yml.enc` | Encrypted application secrets. |
| `config/routes.py` | Application routes. |
| `db/migrate` | Database migrations. |
| `storage` | Local database files and other stored data. |
| `test` | Tests and YAML fixtures. |

See [Configuration](configuration.md) for the boot process, environments, credentials, and database setting precedence.
