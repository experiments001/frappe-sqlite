import unittest
import time

import frappe
import frappe.cache_manager
import frappe.defaults
from frappe.tests import IntegrationTestCase


def sqlite_only_runtime_enabled():
	return (
		frappe.db.db_type == "sqlite"
		and frappe.conf.get("cache_backend") == "local"
		and frappe.conf.get("queue_backend") == "sync"
		and frappe.conf.get("realtime_backend") == "noop"
	)


@unittest.skipUnless(sqlite_only_runtime_enabled(), "requires SQLite-only runtime site config")
class TestSQLiteOnlyRuntime(IntegrationTestCase):
	def test_runtime_backends(self):
		self.assertEqual(frappe.db.db_type, "sqlite")
		self.assertEqual(frappe.conf.get("cache_backend"), "local")
		self.assertEqual(frappe.conf.get("queue_backend"), "sync")
		self.assertEqual(frappe.conf.get("realtime_backend"), "noop")
		self.assertEqual(frappe.db.get_value("User", "Administrator", "name"), "Administrator")

	def test_local_cache(self):
		frappe.cache.set_value("sqlite-only-test", {"ok": True})
		self.assertEqual(frappe.cache.get_value("sqlite-only-test"), {"ok": True})

		frappe.cache.hset("sqlite-only-hash", "key", "value")
		self.assertEqual(frappe.cache.hget("sqlite-only-hash", "key"), "value")

		frappe.cache.rpush("sqlite-only-list", "first")
		frappe.cache.rpush("sqlite-only-list", "second")
		self.assertEqual(frappe.cache.lrange("sqlite-only-list", 0, -1), ["first", "second"])

		frappe.cache.delete_value(["sqlite-only-test", "sqlite-only-hash", "sqlite-only-list"])
		self.assertIsNone(frappe.cache.get_value("sqlite-only-test"))

	def test_local_cache_ttl(self):
		frappe.cache.setex("sqlite-only-ttl", 1, "value")
		self.assertEqual(frappe.cache.get("sqlite-only-ttl"), "value")
		self.assertEqual(frappe.cache.exists("sqlite-only-ttl", shared=True), 1)

		time.sleep(1.1)

		self.assertIsNone(frappe.cache.get("sqlite-only-ttl"))
		self.assertEqual(frappe.cache.exists("sqlite-only-ttl", shared=True), 0)

	def test_metadata_and_defaults_cache(self):
		meta = frappe.get_meta("ToDo")
		self.assertEqual(meta.name, "ToDo")

		frappe.cache_manager.clear_doctype_cache("ToDo")
		meta = frappe.get_meta("ToDo")
		self.assertEqual(meta.name, "ToDo")

		frappe.defaults.set_global_default("sqlite_only_runtime", "ok")
		self.addCleanup(lambda: frappe.defaults.clear_default("sqlite_only_runtime"))

		self.assertEqual(frappe.defaults.get_global_default("sqlite_only_runtime"), "ok")
		frappe.clear_cache()
		self.assertEqual(frappe.defaults.get_global_default("sqlite_only_runtime"), "ok")

	def test_sync_enqueue(self):
		result = frappe.enqueue("frappe.get_site_config")
		self.assertEqual(result.db_type, "sqlite")

	def test_sync_enqueue_after_commit(self):
		events = []

		def mark():
			events.append("ran")

		frappe.enqueue(mark, enqueue_after_commit=True)
		self.assertEqual(events, [])

		frappe.db.commit()
		self.assertEqual(events, ["ran"])

	def test_after_commit_reset_on_rollback(self):
		events = []

		frappe.db.after_commit.add(lambda: events.append("commit"))
		frappe.db.rollback()
		frappe.db.commit()

		self.assertEqual(events, [])

	def test_noop_realtime(self):
		frappe.publish_realtime("sqlite_only_runtime_test", {"ok": True})

	def test_todo_crud_and_filters(self):
		todo = frappe.get_doc(
			{"doctype": "ToDo", "description": "SQLite only runtime test", "priority": "Medium"}
		).insert(ignore_permissions=True)
		self.addCleanup(lambda: frappe.delete_doc("ToDo", todo.name, ignore_permissions=True) if frappe.db.exists("ToDo", todo.name) else None)

		frappe.db.commit()

		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "description"), "SQLite only runtime test")

		todo = frappe.get_doc("ToDo", todo.name)
		todo.description = "SQLite only runtime test updated"
		todo.save(ignore_permissions=True)
		frappe.db.commit()

		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "description"), "SQLite only runtime test updated")

		rows = frappe.get_list(
			"ToDo",
			filters=[["ToDo", "description", "like", "SQLite only runtime%"]],
			fields=["name", "description"],
			order_by="creation desc",
			limit=5,
		)
		self.assertTrue(any(row.name == todo.name for row in rows))

		frappe.delete_doc("ToDo", todo.name, ignore_permissions=True)
		frappe.db.commit()
		self.assertFalse(frappe.db.exists("ToDo", todo.name))
