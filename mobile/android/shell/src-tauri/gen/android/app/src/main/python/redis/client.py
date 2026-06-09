# redis.client shim
class Pipeline:
    def __init__(self, *a, **k): pass
    def execute(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a, **k): pass
