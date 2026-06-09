"""rq compatibility shim for iOS (no Redis server on device)."""

from .job import Job
from .worker import Worker
from .exceptions import NoSuchJobError


class Queue:
    """No-op RQ queue."""

    def __init__(self, *a, **k):
        pass

    def enqueue(self, *a, **k):
        pass

    def enqueue_at(self, *a, **k):
        pass

    def enqueue_in(self, *a, **k):
        pass

    def is_empty(self):
        return True

    def count(self):
        return 0
