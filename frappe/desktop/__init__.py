"""Desktop/local lifecycle helpers for SQLite-backed Frappe runtimes."""

from __future__ import annotations

LOCAL_SQLITE_CONFIG = {
	"db_type": "sqlite",
	"cache_backend": "local",
	"queue_backend": "sync",
	"realtime_backend": "noop",
	"pause_scheduler": 1,
	"disable_async": 1,
}

