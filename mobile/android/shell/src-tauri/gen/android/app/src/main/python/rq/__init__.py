# rq shim for Android (no Redis Queue)
class Callback:
    def __init__(self, *a, **k): pass

class Queue:
    def __init__(self, *a, **k): pass
    def enqueue(self, *a, **k): return None
    def enqueue_at(self, *a, **k): return None
    def dequeue(self, *a, **k): return None
    def fetch_job(self, *a, **k): return None
    def empty(self, *a, **k): pass

class Worker:
    def __init__(self, *a, **k): pass
    def work(self, *a, **k): pass
    def register_birth(self, *a, **k): pass
    def register_death(self, *a, **k): pass

def get_current_job(): return None
