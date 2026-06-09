"""cryptography shim for iOS — minimal fallback.

Many Frappe features won't work without real cryptography,
but the app should still boot for the PoC.
"""


class Fernet:
    def __init__(self, *a, **k):
        raise NotImplementedError("cryptography not available on iOS")


class InvalidToken(Exception):
    pass


def __getattr__(name):
    raise NotImplementedError(f"cryptography.{name} not available on iOS")
