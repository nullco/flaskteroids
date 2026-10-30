# Background jobs

Use a job for work that should happen outside an HTTP request, such as processing
an upload. The web process enqueues the job; a separate worker runs it.

After reading this guide, you will know how to:

- Define a job and enqueue it from your application.
- Start a worker and configure its broker.
- Test scheduling without running a worker.

## Define and enqueue a job

Jobs inherit from `Job` and define `perform`. Put the class under `app/jobs` so
Flaskteroids registers it automatically:

```python
# app/jobs/my_job.py
from flaskteroids.jobs.job import Job


class MyJob(Job):
    def perform(self, user_id):
        print(f"Performing job for user {user_id}")
```

Create an instance and call `perform_later` to enqueue it:

```python
from app.jobs.my_job import MyJob

MyJob().perform_later(user_id=1)
```

This schedules the work; it does not run `perform` in the request. If the job needs
newly saved records, enqueue it after the database transaction commits so the
worker can read them.

## Start a worker

Celery is the default queue adapter. From the application directory, start a
worker in a separate terminal:

```sh
bin/jobs start
```

The script uses the application's `.venv` and works from outside the application
directory too. Run `bin/setup` first if the environment is missing. Extra options
are passed to the Celery worker, for example:

```sh
bin/jobs start --concurrency=2 --loglevel=debug
```

The web process and worker must use the same environment and broker settings.
See your generated `Procfile` and `deploy/README.md` for process examples.

## Configuration

Set `config.jobs` in application or environment configuration:

```python
config.jobs.broker_url = "sqla+sqlite:///storage/jobs_database.db"
config.jobs.result_backend = None
config.jobs.additional_config = {}
```

The local SQLite broker is useful for development. For production, configure a
broker accessible to both the web process and workers.

## Tests

Generated test configuration uses an in-memory adapter, so tests do not need a
running worker or broker. To configure that adapter explicitly:

```python
from flaskteroids.testing import TestQueueAdapter

config.jobs.queue_adapter = TestQueueAdapter
```

Use `assert_enqueued_with` to check scheduling and `perform_enqueued_jobs` to run
jobs enqueued inside its block. See [Testing](../testing.md#jobs-and-mail).

## Registration and application context

Enqueue jobs inside an application context. Requests already provide one, and
workers run jobs in one. For scripts, open a context as shown in
[Configuration](../configuration.md#using-models-and-jobs-in-scripts).
