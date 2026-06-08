from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from frappe.desktop._utils import db_path_for, resolve_sites_path, site_path, sqlite_integrity_check
from frappe.desktop.site_manager import list_sites


def check_site_needs_migration(site_name: str, sites_path: str | Path | None = None) -> dict[str, Any]:
	root = resolve_sites_path(sites_path)
	touched = site_path(site_name, root) / "touched_tables.json"
	return {"site_name": site_name, "needs_migration": not touched.exists(), "reason": "best_effort"}


def migrate_site(site_name: str, sites_path: str | Path | None = None) -> dict[str, Any]:
	root = resolve_sites_path(sites_path)
	if not site_path(site_name, root).exists():
		raise FileNotFoundError(f"Site missing: {site_name}")
	import frappe
	from frappe.migrate import SiteMigration

	old_cwd = Path.cwd()
	try:
		os.chdir(root)
		SiteMigration(skip_search_index=True).run(site=site_name)
	finally:
		os.chdir(old_cwd)
	health = sqlite_integrity_check(db_path_for(site_name, root))
	with frappe.init_site(site=site_name, sites_path=str(root)):
		frappe.clear_cache()
	return {"site_name": site_name, "migrated": True, "health": health}


def migrate_all_sites(sites_path: str | Path | None = None) -> list[dict[str, Any]]:
	root = resolve_sites_path(sites_path)
	results = []
	for site in list_sites(root):
		try:
			results.append(migrate_site(site["site_name"], root))
		except Exception as exc:
			results.append({"site_name": site["site_name"], "migrated": False, "error": str(exc)})
	return results


def _main() -> None:
	parser = argparse.ArgumentParser(description="Local SQLite migration helpers")
	sub = parser.add_subparsers(dest="command", required=True)
	site = sub.add_parser("site")
	site.add_argument("site")
	sub.add_parser("all")
	args = parser.parse_args()
	if args.command == "site":
		print(json.dumps(migrate_site(args.site), indent=2))
	else:
		print(json.dumps(migrate_all_sites(), indent=2))


if __name__ == "__main__":
	_main()
