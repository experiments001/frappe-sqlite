"""Pure-Python shim for psutil (unavailable on Android)."""

LINUX = False


def cpu_count(logical=True):
    import os

    return os.cpu_count() or (4 if logical else 2)


class Process:
    def cpu_affinity(self, cores):
        pass

    def memory_info(self):
        class _Mem:
            rss = 0
            vms = 0

        return _Mem()
