"""Static-only probes; these adapters need not inherit a runtime base class."""

from typing import Any, assert_type

from celery.result import AsyncResult
from flask import Flask

from flaskteroids.configuration import Options
from flaskteroids.declarations import (
    ActionDefinition,
    AssociationDefinition,
    ModelDefinition,
    RuleDefinition,
    VirtualFieldConfig,
    actions_for,
    model_for,
    rules_for,
)
from flaskteroids.jobs.adapters import CeleryQueueAdapter, QueueAdapter
from flaskteroids.jobs.job import Job
from flaskteroids.testing.jobs import EnqueuedJob, TestQueueAdapter


class CustomAdapter:
    def register(self, job_name: str, job_class: type[Job]) -> None:
        pass

    def enqueue(
        self, job_class: type[Job], args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> str:
        return "custom-result"


def enqueue(adapter: QueueAdapter, job_class: type[Job]) -> object:
    adapter.register("example", job_class)
    return adapter.enqueue(job_class, ("value",), {"enabled": True})


def adapter_contract(application: Flask, config: Options, job_class: type[Job]) -> None:
    celery = CeleryQueueAdapter(application, config)
    test = TestQueueAdapter(application, config)
    custom = CustomAdapter()
    enqueue(celery, job_class)
    enqueue(test, job_class)
    enqueue(custom, job_class)
    assert_type(celery.enqueue(job_class, (), {}), AsyncResult)
    assert_type(test.enqueue(job_class, (), {}), EnqueuedJob)
    assert_type(custom.enqueue(job_class, (), {}), str)


def declaration_contract(cls: type) -> None:
    assert_type(model_for(cls), ModelDefinition)
    assert_type(rules_for(cls), RuleDefinition)
    assert_type(actions_for(cls), ActionDefinition)
    association = AssociationDefinition("posts", "has_many", "Post", "author_id")
    model_for(cls).associations[association.name] = association
    field: VirtualFieldConfig = {"read_only": True, "cache": False}
    model_for(cls).virtual_fields["preview"] = field
