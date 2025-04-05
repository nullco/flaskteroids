from abc import ABC, abstractmethod
import flaskteroids.registry as registry


class Job(ABC):

    @abstractmethod
    def perform(self, *args, **kwargs):
        pass

    @classmethod
    def perform_later(cls, *args, **kwargs):
        ns = registry.get(cls)
        task = ns.get('task')
        assert task, 'Task not registered'
        task.delay(*args, **kwargs)
