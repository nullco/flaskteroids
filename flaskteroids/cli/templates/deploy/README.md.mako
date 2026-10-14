# Docker and deployment

Docker support is included by default. Run `bin/setup` first if installation was skipped;
commit your application's `uv.lock`. Builds use its locked environment, not host pip.
Never pass the master key during image build.

```sh
docker build -t my-app .
docker volume create my-app-storage
# Local demonstration only: keep this untracked file restricted.
(umask 077; printf 'FLASKTEROIDS_MASTER_KEY=%s\n' "$(tr -d '\n' < config/master.key)" > .env.production)
docker run --rm -p 8000:8000 --env-file .env.production \
  -v my-app-storage:/app/storage my-app
```

The default `gunicorn wsgi:app ...` command prepares the production database before
launching workers. SQLite and local attachments need persistent writable `/app/storage`.
The image runs unprivileged. Host bind mounts must be writable by the image's app user.
Missing/wrong keys and migration failures prevent web startup.

For a fleet, coordinate preparation once as a release step and override the entrypoint:
```sh
docker run --rm --env-file .env.production -v my-app-storage:/app/storage \
  my-app /app/bin/release migrate
docker run --rm -p 8000:8000 --env-file .env.production \
  -v my-app-storage:/app/storage --entrypoint gunicorn my-app wsgi:app -b 0.0.0.0:8000
```
Automatic preparation is not distributed migration coordination. Other commands bypass it:
`docker run ... my-app celery -A jobs worker --loglevel=info`.
Workers require a reachable `CELERY_BROKER_URL`; this is not provisioned by the framework.

The image sets `FLASK_ENV=production`. `DATABASE_URL` optionally overrides SQLite;
external databases must exist and their drivers must be installed and locked.
`ATTACHMENTS_SERVICE` defaults to local; external storage and SMTP need application
configuration/credentials. `SECRET_KEY_BASE` is optional, not a replacement for the
matching credentials key. `PORT` is for Procfile platforms, not Docker's port 8000.
Procfile is a process example, not consumed by Docker.

The demonstration env file is not a production secret manager. Remove it when finished.
Kamal integration is deferred pending version/configuration/secret/release acceptance.
The old malformed Kamal, unsafe SSH workflow, and duplicate release examples are no longer
generated. Existing projects are not automatically changed; regeneration may overwrite files.
