# redis shim for Android (no Redis server)
from redis import client

class Connection:
    def __init__(self, *a, **k): pass

class UnixDomainSocketConnection:
    def __init__(self, *a, **k): pass

class SSLConnection:
    def __init__(self, *a, **k): pass

class Redis:
    def __init__(self, *a, **k): pass
    def get(self, *a, **k): return None
    def set(self, *a, **k): pass
    def delete(self, *a, **k): pass
    def exists(self, *a, **k): return 0
    def keys(self, *a, **k): return []
    def flushall(self, *a, **k): pass
    def ping(self, *a, **k): pass
    def pubsub(self, *a, **k): return self
    def subscribe(self, *a, **k): pass
    def listen(self, *a, **k): return []
    def pipeline(self, *a, **k): return self
    def execute(self, *a, **k): pass
    def hget(self, *a, **k): return None
    def hset(self, *a, **k): pass
    def hdel(self, *a, **k): pass
    def hgetall(self, *a, **k): return {}
    def lpush(self, *a, **k): pass
    def rpop(self, *a, **k): return None
    def llen(self, *a, **k): return 0
    def lrange(self, *a, **k): return []
    def sadd(self, *a, **k): pass
    def smembers(self, *a, **k): return set()
    def srem(self, *a, **k): pass
    def zadd(self, *a, **k): pass
    def zrange(self, *a, **k): return []
    def expire(self, *a, **k): pass
    def ttl(self, *a, **k): return -1
    def lock(self, *a, **k):
        class Lock:
            def acquire(self, *a, **k): return True
            def release(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a, **k): pass
        return Lock()
    def __enter__(self): return self
    def __exit__(self, *a, **k): pass

class StrictRedis(Redis):
    pass

from_connection_pool = Redis
ConnectionPool = object
