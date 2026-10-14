from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from celery import Celery
from celery.result import AsyncResult

if TYPE_CHECKING:
    from celery.app.task import Task
    from flask import Flask

    from flaskteroids.configuration import Options
    from flaskteroids.jobs.job import Job


class QueueAdapter(Protocol):
    def register(self, job_name: str, job_class: type[Job]) -> None: ...

    def enqueue(
        self, job_class: type[Job], args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> object: ...


class CeleryQueueAdapter:
    def __init__(self, application: Flask, config: Options) -> None:
        self._celery = Celery(application.import_name)
        self._tasks: dict[type[Job], Task] = {}
        self._celery.conf["result_backend"] = config.result_backend
        self._celery.conf["broker_url"] = config.broker_url
        self._celery.conf.update(config.additional_config.to_dict())

        class AppContextTask(self._celery.Task):
            def __call__(self, *args, **kwargs):
                with application.app_context():
                    return self.run(*args, **kwargs)

        self._celery.Task = AppContextTask

    def register(self, job_name: str, job_class: type[Job]) -> None:
        @self._celery.task(name=job_name, shared=False, lazy=False)
        def task(*args, **kwargs):
            return job_class().perform(*args, **kwargs)

        self._tasks[job_class] = task

    def enqueue(
        self, job_class: type[Job], args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> AsyncResult:
        return self._tasks[job_class].delay(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._celery, name)
