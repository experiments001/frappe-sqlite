"""redis compatibility shim for iOS (no Redis server on device)."""

from .exceptions import RedisError, ConnectionError, TimeoutError, AuthenticationError


class Redis:
    """No-op Redis client."""

    def __init__(self, *a, **k):
        pass

    def ping(self):
        return True

    def get(self, key):
        return None

    def set(self, key, value, *a, **k):
        pass

    def delete(self, *keys):
        return 0

    def exists(self, *keys):
        return 0

    def flushall(self):
        pass

    def pubsub(self, *a, **k):
        return _PubSub()

    def pipeline(self, *a, **k):
        return self

    def execute(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class _PubSub:
    def subscribe(self, *a, **k):
        pass

    def listen(self):
        return []

    def get_message(self, *a, **k):
        pass

    def close(self):
        pass
