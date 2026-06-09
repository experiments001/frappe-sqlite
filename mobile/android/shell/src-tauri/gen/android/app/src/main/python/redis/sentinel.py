# redis.sentinel shim
class Sentinel:
    def __init__(self, *a, **k): pass
    def master_for(self, *a, **k):
        from redis import Redis
        return Redis()
