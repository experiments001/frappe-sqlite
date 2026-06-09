# rq.job shim
class Job:
    id = None
    status = None
    @classmethod
    def fetch(cls, *a, **k): return None

class JobStatus:
    QUEUED = "queued"
    FINISHED = "finished"
    FAILED = "failed"
    STARTED = "started"
    DEFERRED = "deferred"
    SCHEDULED = "scheduled"
    STOPPED = "stopped"
    CANCELED = "canceled"
