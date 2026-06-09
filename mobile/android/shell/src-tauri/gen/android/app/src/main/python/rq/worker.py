# rq.worker shim
class DequeueStrategy:
    DEFAULT = "default"
    ROUND_ROBIN = "round_robin"

class StopRequested(Exception): pass

class WorkerStatus:
    STARTED = "started"
    SUSPENDED = "suspended"
    BUSY = "busy"
    IDLE = "idle"
