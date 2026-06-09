class Job:
    def __init__(self, *a, **k):
        pass

    @classmethod
    def fetch(cls, *a, **k):
        return None

    @classmethod
    def create(cls, *a, **k):
        return cls()

    def get_status(self):
        return "finished"

    def save(self):
        pass
