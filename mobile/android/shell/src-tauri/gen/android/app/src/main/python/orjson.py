"""orjson compatibility shim for Android/Chaquopy.

orjson has native Rust extensions that don't build for Android.
This shim wraps the standard json module to provide the orjson API
used by Frappe.
"""

import json
from json import JSONDecodeError

# Option constants (bit flags) — ignored by shim, but must exist
OPT_PASSTHROUGH_DATETIME = 1
OPT_NON_STR_KEYS = 2
OPT_APPEND_NEWLINE = 4
OPT_SORT_KEYS = 8
OPT_STRICT_INTEGER = 16
OPT_OMIT_MICROSECONDS = 32
OPT_SERIALIZE_DATACLASS = 64
OPT_SERIALIZE_UUID = 128
OPT_SERIALIZE_NUMPY = 256


def loads(data):
    """Parse JSON string to Python object."""
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return json.loads(data)


def dumps(obj, default=None, option=None):
    """Serialize Python object to JSON bytes.

    orjson returns bytes; we mimic that by encoding the json string.
    The `option` flags are ignored (standard json doesn't support them).
    The `default` callback is passed through.
    """
    kwargs = {}
    if default is not None:
        kwargs["default"] = default
    # option flags are ignored — standard json has no equivalents
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), **kwargs).encode("utf-8")


# Expose everything else from json module for safe_exec.py vars(orjson)
for _key, _val in vars(json).items():
    if not _key.startswith("_") and _key not in globals():
        globals()[_key] = _val
